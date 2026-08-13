import json
import logging
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# 이 파일의 형제 모듈(columns.py, db.py 등)은 상대/패키지 임포트가 아니라
# 평범한 최상위 임포트로 서로를 참조한다. `cd backend/receiver && uvicorn
# main:app`처럼 실행하면 파이썬이 스크립트 디렉터리를 자동으로
# sys.path에 넣어주지만, 저장소 루트에서 `uvicorn
# backend.receiver.main:app`으로 패키지 경로를 통해 임포트하면 그 자동
# 추가가 일어나지 않는다. 두 실행 방식을 모두 지원하기 위해 이 파일의
# 디렉터리를 명시적으로 sys.path에 추가한다.
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import columns
import db
import extraction
import mail_source
import priority as priority_module
import review

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clovis.receiver")

app = FastAPI(title="Clovis Receiver API")

# 프론트(정적 서버, 5500번 포트 등)에서 직접 fetch할 수 있도록 로컬 개발
# 단계에서는 모든 출처를 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIOS_DIR = Path(__file__).parent / "scenarios"


@app.on_event("startup")
def _on_startup() -> None:
    db.init_db()


class ExtractRequest(BaseModel):
    source: str = "paste"
    scenario_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None


class CasePayload(BaseModel):
    case_id: str
    fields: dict


class CompareRequest(BaseModel):
    cases: list[CasePayload]


class DecisionRequest(BaseModel):
    case_id: str
    ship_call_sign: Optional[str] = None
    fields: list[dict] = []
    mail_reference: Optional[str] = None
    user: str = "local-user"
    reason: Optional[str] = None


def _load_scenario(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"시나리오를 찾을 수 없습니다: {scenario_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _list_scenarios() -> list[dict]:
    result = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        result.append(
            {
                "id": data["id"],
                "title": data["title"],
                "category": data.get("category"),
                "summary": data.get("summary"),
            }
        )
    return result


# ---------------------------------------------------------------------
# 보조 엔드포인트 (예시 목록, 헬스체크 등)
# ---------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "receiver"}


@app.get("/columns")
def get_columns() -> dict:
    return {"columns": columns.ALL_COLUMNS}


@app.get("/scenarios")
def list_scenarios() -> dict:
    return {"scenarios": _list_scenarios()}


@app.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return _load_scenario(scenario_id)


# ---------------------------------------------------------------------
# Receiver 핵심 API
# ---------------------------------------------------------------------


@app.post("/api/receiver/extract")
def api_extract(payload: ExtractRequest) -> dict:
    """메일 원문 -> 추출 결과.

    mode="mock": AI 연동이 설정되지 않아 로컬 테스트 경로를 사용함(정상).
    mode="openai": 실제 Structured Outputs 호출 성공.
    mode="error": AI 연동은 설정돼 있지만 호출이 실패함. cases는 빈
        배열이며, 프론트는 "AI 추출 실패 - 수동 확인 필요"를 노출해야
        하고 mock으로 자동 대체하지 않는다.
    """
    try:
        mail = mail_source.get_target_email(
            source=payload.source,
            scenario_id=payload.scenario_id,
            raw_text=payload.body,
            subject=payload.subject,
        )
    except mail_source.MailSourceError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))

    result = extraction.extract_cases(mail["scenario_id"], mail["body"])
    return {
        "mail": mail,
        "mode": result["mode"],
        "error": result["error"],
        "cases": result["cases"],
    }


@app.post("/api/receiver/compare")
def api_compare(payload: CompareRequest) -> dict:
    """추출 결과(/extract가 반환한 cases 그대로) -> DB 대조 + 검토 카드.

    각 카드에 이미 승인/반려된 이력이 있으면 decision 필드로 알려준다.
    """
    cards = []
    for case in payload.cases:
        card = review.build_review_card({"case_id": case.case_id, "fields": case.fields})
        card["decision"] = db.get_latest_decision(case.case_id)
        cards.append(card)
    return {"cases": cards}


@app.post("/api/receiver/approve")
def api_approve(payload: DecisionRequest) -> dict:
    """변경 건 승인 -> SQLite ships 테이블 반영 + change_history에 기록."""
    if not payload.ship_call_sign:
        raise HTTPException(status_code=400, detail="ship_call_sign이 필요합니다.")

    changes = {
        row["key"]: row["new_value"]
        for row in payload.fields
        if row.get("status") == "changed" and row.get("new_value") not in (None, "")
    }

    updated = db.apply_approved_changes(payload.ship_call_sign, changes)
    if updated is None:
        raise HTTPException(status_code=404, detail="DB에 등록되지 않은 선박은 승인할 수 없습니다.")

    history = db.record_history(
        case_id=payload.case_id,
        ship_call_sign=payload.ship_call_sign,
        action="approved",
        changed_by=payload.user,
        mail_reference=payload.mail_reference,
        changes=changes,
    )
    logger.info(
        "[APPROVE] case_id=%s ship=%s by=%s changes=%s",
        payload.case_id,
        payload.ship_call_sign,
        payload.user,
        changes,
    )
    return {"status": "approved", "ship": updated, "history": history}


@app.post("/api/receiver/reject")
def api_reject(payload: DecisionRequest) -> dict:
    """변경 건 반려 -> change_history에만 기록(ships 테이블은 건드리지 않음)."""
    changes = {
        row["key"]: row.get("new_value") for row in payload.fields if row.get("status") == "changed"
    }
    history = db.record_history(
        case_id=payload.case_id,
        ship_call_sign=payload.ship_call_sign,
        action="rejected",
        changed_by=payload.user,
        mail_reference=payload.mail_reference,
        changes=changes,
    )
    logger.info(
        "[REJECT] case_id=%s ship=%s by=%s reason=%s",
        payload.case_id,
        payload.ship_call_sign,
        payload.user,
        payload.reason,
    )
    return {"status": "rejected", "history": history}


@app.get("/api/receiver/dashboard")
def api_dashboard(sort: str = "priority") -> dict:
    """준비된 mock 시나리오(오늘의 수신함 대용)를 처리해, 아직 승인/반려
    되지 않은 건만 우선순위 순으로 정렬해 반환한다."""
    all_cards = []
    for scenario_meta in _list_scenarios():
        scenario = _load_scenario(scenario_meta["id"])
        result = extraction.extract_cases(scenario["id"], scenario["mail"]["body"])
        if result["mode"] == "error":
            logger.warning("대시보드 집계 중 추출 실패, 이 시나리오는 건너뜁니다: %s", scenario["id"])
            continue
        for case in result["cases"]:
            if db.get_latest_decision(case["case_id"]) is not None:
                continue  # 이미 승인/반려된 건은 대기 목록에서 제외
            card = review.build_review_card(case)
            card["scenario_id"] = scenario["id"]
            card["scenario_title"] = scenario["title"]
            all_cards.append(card)

    sorted_cards = priority_module.sort_cases(all_cards, sort_key=sort)
    return {"sort": sort, "cases": sorted_cards}


@app.get("/api/receiver/history")
def api_history(limit: int = 50) -> dict:
    """감사 추적 확인용 보조 엔드포인트. change_history를 최신순으로 반환한다."""
    return {"history": db.list_history(limit=limit)}

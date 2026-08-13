"""수신 메일에서 핵심 필드를 추출하는 로직.

## 두 개의 경로

1. mock_extract_email_fields / unrecognized_case
   "API 연동 전 임시 코드"가 아니라 아래 두 가지 목적을 위해 계속
   유지되는 정식 경로다.
   - API 키 없이도 서비스 전체 흐름(추출 -> 대조 -> 검토 -> 우선순위
     대시보드)이 기동/동작하는지 확인하는 로컬 테스트 경로.
   - extract_cases()가 "AI 연동이 아예 설정되지 않은 경우"에 자동으로
     쓰는 경로.
   주의: API 키가 설정되어 있는데 실제 호출이 실패한 경우에는 이 mock
   경로로 자동 대체하지 않는다. 그 경우는 extract_cases()가
   mode="error"를 반환해 "AI 추출 실패"를 그대로 노출한다(요구사항 9).

2. extract_email_fields (openai_client.call_structured_extraction 사용)
   실제 연동 경로. Structured Outputs로 mock과 동일한 필드 스키마를
   반환하므로 두 경로를 자유롭게 스위칭할 수 있다.

## 반환 스키마 (공통)

    [
        {"case_id": str, "fields": {"<field_key>": FIELD, ...}},
        ...
    ]

    FIELD = {
        "value": str | None,
        "evidence": str | None,        # value가 나온 원문 발췌
        "confidence": float | None,    # 0.0~1.0, 값이 없으면 None
        "extraction_failed": bool,     # True면 value/evidence/confidence 모두 None
    }

필드 키는 columns.CORE_EXTRACT_KEYS와 동일하다: port_name, call_sign,
ship_name, arrival_datetime, next_port, previous_port, ship_id,
cargo_volume.
"""

import logging
from pathlib import Path

import openai_client
import secret_manager
from columns import CORE_EXTRACT_KEYS

logger = logging.getLogger("clovis.receiver.extraction")

_PROMPT_PATH = Path(__file__).resolve().parent / "PROMPT.md"
_system_prompt_cache = None


def _system_prompt() -> str:
    global _system_prompt_cache
    if _system_prompt_cache is None:
        _system_prompt_cache = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""
    return _system_prompt_cache


def _empty_fields():
    return {
        key: {"value": None, "evidence": None, "confidence": None, "extraction_failed": True}
        for key in CORE_EXTRACT_KEYS
    }


def _case(case_id, **overrides):
    """overrides: key=(value, evidence, confidence) 3-튜플."""
    fields = _empty_fields()
    for key, (value, evidence, confidence) in overrides.items():
        fields[key] = {
            "value": value,
            "evidence": evidence,
            "confidence": confidence,
            "extraction_failed": False,
        }
    return {"case_id": case_id, "fields": fields}


# 시나리오 메일을 "실제로 AI가 읽었다면 이렇게 추출됐을 것"이라고 가정한
# 값 + 근거 문장 + 확신도. 시나리오 mail.body의 문장과 그대로 대응한다.
_MOCK_CASES = {
    "scenario_eta_change": [
        _case(
            "scenario_eta_change-0",
            port_name=("부산항", "한라에이스호(호출부호 D7HL2)의 부산항 입항 일정이 변경되어 안내드립니다.", 0.97),
            call_sign=("D7HL2", "한라에이스호(호출부호 D7HL2)의 부산항 입항 일정이 변경되어 안내드립니다.", 0.98),
            ship_name=("한라에이스호", "한라에이스호(호출부호 D7HL2)의 부산항 입항 일정이 변경되어 안내드립니다.", 0.98),
            arrival_datetime=(
                "2026-08-17 14:00",
                "당초 2026-08-15 09:00 입항 예정이었던 일정이 2026-08-17 14:00으로 약 48시간 지연될 예정입니다.",
                0.93,
            ),
        ),
    ],
    "scenario_cargo_change": [
        _case(
            "scenario_cargo_change-0",
            port_name=("인천항", "동해퍼스트호(호출부호 D8DF7) 인천항 기항 건 관련하여 화물량 변경 사항 안내드립니다.", 0.96),
            call_sign=("D8DF7", "동해퍼스트호(호출부호 D8DF7) 인천항 기항 건 관련하여 화물량 변경 사항 안내드립니다.", 0.98),
            ship_name=("동해퍼스트호", "동해퍼스트호(호출부호 D8DF7) 인천항 기항 건 관련하여 화물량 변경 사항 안내드립니다.", 0.98),
            arrival_datetime=("2026-08-16 15:00", "입항 일시(2026-08-16 15:00)는 변경 없이 동일하게 유지됩니다.", 0.9),
            cargo_volume=("950 TEU", "당초 1,200 TEU였던 예상 화물량이 950 TEU로 조정되었습니다.", 0.88),
        ),
    ],
    "scenario_combined_change": [
        _case(
            "scenario_combined_change-0",
            port_name=("광양항", "광양항 입항 일정이 2026-08-20 06:00에서 2026-08-21 11:00으로 하루 이상 지연됩니다.", 0.95),
            call_sign=("D9PS5", "1. 태평양스타호(호출부호 D9PS5)", 0.98),
            ship_name=("태평양스타호", "1. 태평양스타호(호출부호 D9PS5)", 0.98),
            arrival_datetime=(
                "2026-08-21 11:00",
                "광양항 입항 일정이 2026-08-20 06:00에서 2026-08-21 11:00으로 하루 이상 지연됩니다.",
                0.93,
            ),
            cargo_volume=("1,050 TEU", "화물량은 800 TEU에서 1,050 TEU로 증가하며", 0.9),
            next_port=("칭다오항", "차항지는 상하이항에서 칭다오항으로 변경됩니다.", 0.91),
        ),
        _case(
            "scenario_combined_change-1",
            port_name=("부산항", "부산항 입항 일정이 2026-08-10 09:00으로 확정되었습니다.", 0.9),
            call_sign=("D6EG9", "2. 은하글로리호(호출부호 D6EG9)", 0.97),
            ship_name=("은하글로리호", "2. 은하글로리호(호출부호 D6EG9)", 0.97),
            arrival_datetime=("2026-08-10 09:00", "부산항 입항 일정이 2026-08-10 09:00으로 확정되었습니다.", 0.9),
        ),
        _case(
            "scenario_combined_change-2",
            call_sign=("D8DF7", "3. 동해퍼스트호(호출부호 D8DF7)", 0.97),
            ship_name=("동해퍼스트호", "3. 동해퍼스트호(호출부호 D8DF7)", 0.97),
            cargo_volume=("5,500 TEU", "화물량이 5,500 TEU로 대폭 증가하였습니다.", 0.87),
        ),
    ],
}


def mock_extract_email_fields(scenario_id, mail_body=""):
    """로컬 테스트/폴백 경로. 시나리오별로 미리 정의된 값+근거+확신도를
    반환한다(실제로 mail_body를 파싱하지 않는다)."""
    cases = _MOCK_CASES.get(scenario_id)
    if cases is None:
        raise ValueError(f"등록되지 않은 시나리오입니다: {scenario_id}")
    return cases


def unrecognized_case():
    """scenario_id 없이 임의로 붙여넣은 원문 등, 준비된 mock 데이터가 없는
    메일에 대해 정직하게 "아무것도 추출하지 못했다"를 나타내는 케이스.
    값을 임의로 채우지 않는다는 원칙을 지키기 위해 모든 필드를
    extraction_failed=True로 둔다."""
    return _case("unrecognized-0")


class ExtractionError(Exception):
    pass


def _build_user_prompt(mail_body: str) -> str:
    return (
        "아래는 처리 대상으로 분류된 수신 메일 원문입니다. PROMPT.md의 규칙에 따라 "
        "선박/일정 변경 건을 추출하세요.\n\n"
        "----- 메일 원문 시작 -----\n"
        f"{mail_body}\n"
        "----- 메일 원문 끝 -----"
    )


def extract_email_fields(scenario_id, mail_body):
    """실제 OpenAI Structured Outputs 연동.

    scenario_id는 이 경로에서 쓰이지 않는다(실제 메일은 mail_body만
    가지고 있다). mock과 시그니처를 맞추기 위해 인자로만 받는다.
    """
    config = secret_manager.get_openai_config()
    if not config["api_key"]:
        raise ExtractionError("OPENAI_API_KEY가 설정되지 않았습니다.")

    try:
        result = openai_client.call_structured_extraction(_system_prompt(), _build_user_prompt(mail_body), config)
    except openai_client.OpenAIError as exc:
        raise ExtractionError(str(exc)) from exc

    cases = []
    for idx, fields in enumerate(result["cases"]):
        cases.append({"case_id": f"openai-{idx}", "fields": fields})
    return cases


def extract_cases(scenario_id, mail_body):
    """main.py의 /api/receiver/extract가 호출하는 단일 진입점.

    반환: {"cases": [...], "mode": "mock" | "openai" | "error", "error": str | None}

    - AI 연동이 설정되지 않은 경우(mode="mock")는 정상적인 로컬 테스트
      경로이지 에러가 아니다.
    - AI 연동이 설정되어 있는데 호출이 실패한 경우(mode="error")는 mock
      으로 자동 대체하지 않는다. 사용자가 실패를 알 수 있어야 한다.
    """
    if not secret_manager.is_ai_configured():
        cases = mock_extract_email_fields(scenario_id, mail_body) if scenario_id else [unrecognized_case()]
        return {"cases": cases, "mode": "mock", "error": None}

    try:
        cases = extract_email_fields(scenario_id, mail_body)
        return {"cases": cases, "mode": "openai", "error": None}
    except ExtractionError as exc:
        logger.error("AI 추출 실패 (scenario_id=%s): %s", scenario_id, exc)
        return {"cases": [], "mode": "error", "error": str(exc)}

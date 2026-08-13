"""물류 변경 건의 위험, 업무 영향, 대응안과 커뮤니케이션 초안을 만든다.

해커톤 데모에서는 판단 근거를 설명할 수 있어야 하므로 위험 점수와 추천
대응안은 명시적인 규칙으로 계산한다. 메일 필드 추출은 AI가 담당하고,
이 모듈은 AI가 추출한 값과 기존 DB의 차이만 사용한다.
"""

from __future__ import annotations

import logging
from typing import Any

import ai_decision
import secret_manager
import validation

logger = logging.getLogger("clovis.receiver.decision_support")


ACTION_CATALOG = {
    "maintain": {
        "title": "기존 운송 유지",
        "description": "현재 운송 계획을 유지하고 이해관계자에게 변경 일정만 공유합니다.",
        "cost": "추가비용 낮음",
        "lead_time": "즉시 실행",
        "english": "maintain the current transport plan and monitor the revised schedule",
    },
    "alternative_vessel": {
        "title": "대체 선박 검토",
        "description": "동일 구간의 대체 선복과 연결 일정을 확인합니다.",
        "cost": "추가비용 중간",
        "lead_time": "선복 확인 필요",
        "english": "secure an alternative vessel for the affected cargo",
    },
    "emergency_air": {
        "title": "항공 긴급운송",
        "description": "납기 영향이 큰 핵심 물량을 항공으로 전환합니다.",
        "cost": "추가비용 높음",
        "lead_time": "가장 빠름",
        "english": "switch the critical cargo to emergency air freight",
    },
    "partial_air": {
        "title": "일부 물량만 항공 전환",
        "description": "핵심 부품만 항공으로 보내 비용과 납기 위험을 함께 줄입니다.",
        "cost": "추가비용 중간",
        "lead_time": "빠름",
        "english": "move only the critical portion by air while keeping the remaining cargo on the current plan",
    },
    "renegotiate": {
        "title": "고객사 납기 재협의",
        "description": "변경 근거를 공유하고 현실적인 납품 일정을 재합의합니다.",
        "cost": "운송비 증가 낮음",
        "lead_time": "고객 협의 필요",
        "english": "renegotiate the delivery date with the customer using the confirmed delay evidence",
    },
}

ENGLISH_FIELD_LABELS = {
    "port_name": "Port",
    "call_sign": "Call sign",
    "ship_name": "Vessel",
    "arrival_datetime": "ETA",
    "next_port": "Next port",
    "previous_port": "Previous port",
    "ship_id": "Vessel ID",
    "cargo_volume": "Cargo volume",
}


def _field_map(card: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row.get("key"): row for row in card.get("fields", [])}


def _schedule_delta_days(rows: dict[str, dict[str, Any]]) -> float | None:
    row = rows.get("arrival_datetime", {})
    if row.get("status") != "changed":
        return None
    old_dt = validation.normalize_datetime(row.get("old_value"))
    new_dt = validation.normalize_datetime(row.get("new_value"))
    if old_dt is None or new_dt is None:
        return None
    return (new_dt - old_dt).total_seconds() / 86400


def _changed_summary(card: dict[str, Any]) -> list[str]:
    result = []
    for row in card.get("fields", []):
        if row.get("status") != "changed":
            continue
        old_value = row.get("old_value") or "미등록"
        new_value = row.get("new_value") or "정보 없음"
        result.append(f"{row.get('label', row.get('key'))}: {old_value} → {new_value}")
    return result


def build_decision_support(card: dict[str, Any], *, allow_ai: bool = True) -> dict[str, Any]:
    """검토 카드에 설명 가능한 물류 위험도와 대응안 후보를 추가한다."""
    rows = _field_map(card)
    summary = card.get("summary", {})
    warnings = card.get("warnings", [])
    warning_types = {warning.get("type") for warning in warnings}
    schedule_delta = _schedule_delta_days(rows)
    cargo_change = summary.get("cargo_change_percent") or 0
    days_until_arrival = summary.get("days_until_arrival")

    score = 8.0
    reasons: list[str] = []
    impacts: list[dict[str, str]] = []

    if schedule_delta is not None:
        if schedule_delta > 0:
            points = min(42.0, schedule_delta * 14)
            score += points
            reasons.append(f"입항 {schedule_delta:.1f}일 지연 +{points:.0f}")
            impacts.append(
                {
                    "area": "납기",
                    "level": "high" if schedule_delta >= 2 else "medium",
                    "message": f"후속 운송 및 고객 납기가 약 {schedule_delta:.1f}일 밀릴 수 있습니다.",
                }
            )
        elif schedule_delta < 0:
            score += 6
            reasons.append("입항 조기 도착 +6")
            impacts.append(
                {
                    "area": "창고·하역",
                    "level": "medium",
                    "message": "조기 입항에 맞춰 하역 인력과 보관 공간을 앞당겨 확보해야 합니다.",
                }
            )

    if cargo_change:
        points = min(28.0, cargo_change * 0.45)
        score += points
        reasons.append(f"화물량 {cargo_change:.1f}% 변동 +{points:.0f}")
        impacts.append(
            {
                "area": "선복·장비",
                "level": "high" if cargo_change >= 30 else "medium",
                "message": f"화물량 {cargo_change:.1f}% 변동으로 선복·컨테이너·하역 장비 재확인이 필요합니다.",
            }
        )

    if rows.get("next_port", {}).get("status") == "changed":
        score += 18
        reasons.append("차항지 변경 +18")
        impacts.append(
            {
                "area": "경로·통관",
                "level": "high",
                "message": "후속 육상운송, 통관 서류, 고객 인도 경로를 다시 계획해야 합니다.",
            }
        )

    if days_until_arrival is not None and 0 <= days_until_arrival <= 5:
        points = max(5.0, (5 - days_until_arrival) * 4)
        score += points
        reasons.append(f"입항 임박 +{points:.0f}")

    if "over_capacity" in warning_types:
        score += 35
        reasons.append("최대 적재량 초과 +35")
        impacts.append(
            {
                "area": "운송 실행",
                "level": "critical",
                "message": "현재 선박의 최대 적재량을 초과해 분할 선적 또는 대체 선복이 필요합니다.",
            }
        )
    if "past_arrival" in warning_types:
        score += 25
        reasons.append("과거 일정 입력 +25")
        impacts.append(
            {
                "area": "데이터 품질",
                "level": "high",
                "message": "과거 일정이 감지되었습니다. 원문과 운영 시스템을 즉시 재확인해야 합니다.",
            }
        )
    if card.get("db_missing"):
        score += 20
        reasons.append("DB 미등록 +20")

    score = min(100, round(score))
    if score >= 75:
        level, label = "critical", "긴급"
    elif score >= 50:
        level, label = "high", "높음"
    elif score >= 30:
        level, label = "medium", "주의"
    else:
        level, label = "low", "낮음"

    if not impacts:
        impacts.append(
            {
                "area": "운영",
                "level": "low",
                "message": "즉각적인 공급망 영향은 낮으며 변경 일정 모니터링으로 대응 가능합니다.",
            }
        )

    if "over_capacity" in warning_types or rows.get("next_port", {}).get("status") == "changed":
        ranked_actions = ["alternative_vessel", "partial_air", "renegotiate"]
    elif "past_arrival" in warning_types:
        ranked_actions = ["renegotiate", "maintain", "alternative_vessel"]
    elif schedule_delta and schedule_delta >= 2:
        ranked_actions = ["partial_air", "emergency_air", "renegotiate"]
    elif level == "medium":
        ranked_actions = ["maintain", "partial_air", "renegotiate"]
    else:
        ranked_actions = ["maintain", "renegotiate", "alternative_vessel"]

    actions = []
    for index, action_id in enumerate(ranked_actions):
        action = dict(ACTION_CATALOG[action_id])
        action.update(
            {
                "id": action_id,
                "recommended": index == 0,
                "reason": (
                    "위험도와 예상 영향을 함께 줄이는 1순위 대응입니다."
                    if index == 0
                    else "비용·납기 조건에 따라 선택할 수 있는 대안입니다."
                ),
            }
        )
        actions.append(action)

    if "over_capacity" in warning_types:
        similar_case = {
            "title": "유사 사례 · 선복 용량 초과 대응",
            "similarity": 91,
            "situation": "화물량 급증으로 기존 선박 적재 한도를 초과한 건",
            "response": "대체 선복 확보 후 핵심 물량을 우선 배정",
            "outcome": "납기 지연을 1일 이내로 제한하고 초과 비용을 사전 승인",
        }
    elif schedule_delta and schedule_delta >= 2:
        similar_case = {
            "title": "유사 사례 · 기상 악화 48시간 지연",
            "similarity": 88,
            "situation": "태풍으로 입항이 이틀 지연되어 핵심 부품 납기 위험 발생",
            "response": "핵심 물량 15%만 항공 전환하고 잔여 물량은 기존 선박 유지",
            "outcome": "고객 라인스톱 없이 추가 운송비를 전량 항공 대비 63% 절감",
        }
    elif rows.get("next_port", {}).get("status") == "changed":
        similar_case = {
            "title": "유사 사례 · 차항지 변경",
            "similarity": 84,
            "situation": "기항지 변경으로 통관·육상운송 경로 재설계 필요",
            "response": "대체 선박 검토와 동시에 현지 운송사·통관사 일정 재확인",
            "outcome": "서류 오류 없이 변경 항만에서 당일 반출 완료",
        }
    else:
        similar_case = {
            "title": "유사 사례 · 경미한 운영정보 변경",
            "similarity": 76,
            "situation": "화물량 또는 일정의 경미한 변동이 접수된 건",
            "response": "기존 운송을 유지하고 변경 근거를 이해관계자에게 공유",
            "outcome": "추가 비용 없이 운영 DB와 고객 안내를 당일 갱신",
        }

    fallback = {
        "risk": {"score": score, "level": level, "label": label, "reasons": reasons},
        "impacts": impacts,
        "actions": actions,
        "recommended_action_id": ranked_actions[0],
        "changed_summary": _changed_summary(card),
        "similar_case": similar_case,
        "engine": "explainable-demo-fallback-v1",
        "analysis_mode": "demo_fallback",
    }

    if not allow_ai or not ai_decision.is_available():
        return fallback

    try:
        result = ai_decision.analyze(card, ACTION_CATALOG)
        ranked_actions = []
        for action_id in result.get("ranked_action_ids", []):
            if action_id in ACTION_CATALOG and action_id not in ranked_actions:
                ranked_actions.append(action_id)
        for action_id in fallback["recommended_action_id"], "maintain", "renegotiate", "alternative_vessel":
            if action_id not in ranked_actions:
                ranked_actions.append(action_id)
        ranked_actions = ranked_actions[:3]
        reason_by_id = {row.get("id"): row.get("reason") for row in result.get("action_reasons", [])}
        actions = []
        for index, action_id in enumerate(ranked_actions):
            action = dict(ACTION_CATALOG[action_id])
            action.update(
                {
                    "id": action_id,
                    "recommended": index == 0,
                    "reason": reason_by_id.get(action_id) or "AI가 변경 근거와 예상 영향을 종합해 제안했습니다.",
                }
            )
            actions.append(action)
        fallback.update(
            {
                "risk": {
                    "score": result["risk_score"],
                    "level": result["risk_level"],
                    "label": result["risk_label"],
                    "summary": result["risk_summary"],
                    "reasons": result["reasons"],
                },
                "impacts": result["impacts"],
                "actions": actions,
                "recommended_action_id": ranked_actions[0],
                "engine": secret_manager.get_openai_config()["model"],
                "analysis_mode": "ai",
            }
        )
        return fallback
    except Exception as exc:  # AI 실패 시 검토 화면 자체는 유지하되 실패를 명시한다.
        logger.exception("AI 위험 분석 실패: %s", exc)
        fallback["analysis_mode"] = "fallback_after_ai_error"
        fallback["ai_error"] = str(exc)
        return fallback


def build_response_package(
    card: dict[str, Any], selected_action_id: str | None = None, mail_subject: str | None = None
) -> dict[str, Any]:
    """선택된 대응안을 바탕으로 영문 회신과 한국어 내부 보고를 만든다."""
    support = card.get("decision_support") or build_decision_support(card)
    action_id = selected_action_id or support["recommended_action_id"]
    action = ACTION_CATALOG.get(action_id, ACTION_CATALOG[support["recommended_action_id"]])
    ship = card.get("ship", {})
    ship_name = ship.get("ship_name") or "the subject vessel"
    call_sign = ship.get("call_sign") or "N/A"
    changes = support.get("changed_summary") or ["확인 가능한 변경 필드 없음"]
    risk = support["risk"]

    english_changes = []
    for row in card.get("fields", []):
        if row.get("status") == "changed":
            english_label = ENGLISH_FIELD_LABELS.get(row.get("key"), row.get("key", "Field"))
            english_changes.append(
                f"- {english_label}: {row.get('old_value') or 'not registered'} -> "
                f"{row.get('new_value') or 'not available'}"
            )
    if not english_changes:
        english_changes = ["- No confirmed database changes were identified."]

    english_subject = f"[Action Required] Logistics change confirmation - {ship_name} ({call_sign})"
    english_body = "\n".join(
        [
            "Dear Partner,",
            "",
            f"We have reviewed the latest update for {ship_name} (call sign: {call_sign}).",
            "The confirmed changes against our current operation data are:",
            *english_changes,
            "",
            f"Based on the current impact assessment, we propose to {action['english']}.",
            "Please confirm the revised information and advise whether any additional operational constraints apply.",
            "",
            "Best regards,",
            "Clovis Logistics Operations",
        ]
    )

    impact_lines = [f"- {item['area']}: {item['message']}" for item in support.get("impacts", [])]
    report_title = f"[물류 변경 보고] {ship_name} ({call_sign})"
    report_body = "\n".join(
        [
            f"1. 수신 메일: {mail_subject or '물류 변경 안내 메일'}",
            f"2. 위험도: {risk['label']} ({risk['score']}/100)",
            "3. DB 대비 변경사항",
            *[f"- {line}" for line in changes],
            "4. 예상 업무 영향",
            *impact_lines,
            f"5. 권고 대응: {action['title']}",
            f"- {action['description']}",
            "6. 담당자 확인사항",
            "- 변경안 승인 후 운영 DB 반영",
            "- 해외 파트너 회신 및 고객 납기 영향 공유",
        ]
    )

    fallback = {
        "selected_action_id": action_id,
        "selected_action": action,
        "english_reply": {"subject": english_subject, "body": english_body},
        "korean_report": {"title": report_title, "body": report_body},
        "source": "confirmed-changes-and-selected-action",
        "generation_mode": "demo_fallback",
    }

    if not ai_decision.is_available():
        return fallback

    try:
        result = ai_decision.generate_response_package(card, support, action, mail_subject)
        fallback.update(
            {
                "english_reply": {"subject": result["english_subject"], "body": result["english_body"]},
                "korean_report": {"title": result["korean_title"], "body": result["korean_body"]},
                "source": "ai-generated-from-confirmed-changes",
                "generation_mode": "ai",
            }
        )
        return fallback
    except Exception as exc:
        logger.exception("AI 회신/보고 생성 실패: %s", exc)
        fallback["generation_mode"] = "fallback_after_ai_error"
        fallback["ai_error"] = str(exc)
        return fallback

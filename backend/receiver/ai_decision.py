"""확정된 변경 데이터만 사용해 AI 위험 분석과 커뮤니케이션을 생성한다.

메일 원문 속 지시문은 이 모듈에 전달하지 않는다. AI는 추출 후 DB와 대조된
구조화 데이터만 받아 위험도와 대응안을 판단하므로 프롬프트 인젝션 표면을
줄이고, 화면에는 판단 근거를 함께 노출한다.
"""

from __future__ import annotations

import json

import openai_client
import secret_manager


ACTION_IDS = ["maintain", "alternative_vessel", "emergency_air", "partial_air", "renegotiate"]

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_score": {"type": "integer", "minimum": 0, "maximum": 100},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
        "risk_label": {"type": "string", "enum": ["낮음", "주의", "높음", "긴급"]},
        "risk_summary": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5},
        "impacts": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "level": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                    "message": {"type": "string"},
                },
                "required": ["area", "level", "message"],
                "additionalProperties": False,
            },
        },
        "ranked_action_ids": {
            "type": "array",
            "items": {"type": "string", "enum": ACTION_IDS},
            "minItems": 3,
            "maxItems": 3,
        },
        "action_reasons": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ACTION_IDS},
                    "reason": {"type": "string"},
                },
                "required": ["id", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "risk_score",
        "risk_level",
        "risk_label",
        "risk_summary",
        "reasons",
        "impacts",
        "ranked_action_ids",
        "action_reasons",
    ],
    "additionalProperties": False,
}

RESPONSE_PACKAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "english_subject": {"type": "string"},
        "english_body": {"type": "string"},
        "korean_title": {"type": "string"},
        "korean_body": {"type": "string"},
    },
    "required": ["english_subject", "english_body", "korean_title", "korean_body"],
    "additionalProperties": False,
}


def is_available() -> bool:
    return secret_manager.is_ai_configured()


def _card_facts(card: dict) -> dict:
    changed = []
    for row in card.get("fields", []):
        if row.get("status") == "changed":
            changed.append(
                {
                    "key": row.get("key"),
                    "label": row.get("label"),
                    "old_value": row.get("old_value"),
                    "new_value": row.get("new_value"),
                    "confidence": row.get("confidence"),
                    "evidence": row.get("evidence"),
                }
            )
    return {
        "ship": card.get("ship"),
        "db_missing": card.get("db_missing"),
        "changed_fields": changed,
        "warnings": card.get("warnings"),
        "numeric_summary": card.get("summary"),
    }


def analyze(card: dict, action_catalog: dict) -> dict:
    config = secret_manager.get_openai_config()
    if not config["api_key"]:
        raise openai_client.OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

    system_prompt = """당신은 완성차·부품 국제물류 관제 전문가다.
제공된 DB 대비 확정 변경 데이터만 근거로 위험도, 업무 영향, 대응 우선순위를 분석하라.
추측한 화물 중요도, 고객 생산계획, 비용을 사실처럼 쓰지 마라.
불확실하면 이유에 '추가 확인 필요'를 명시하라.
위험 점수는 납기, 일정 변경폭, 입항 임박, 경로/통관, 용량 초과, 데이터 품질을 종합한다.
대응안은 제공된 action_catalog의 ID 중 서로 다른 3개만 순위화한다.
모든 설명은 간결한 한국어로 작성한다."""
    user_payload = {"facts": _card_facts(card), "action_catalog": action_catalog}
    return openai_client.call_structured_json(
        system_prompt,
        json.dumps(user_payload, ensure_ascii=False, indent=2),
        config,
        schema=DECISION_SCHEMA,
        schema_name="logistics_decision_analysis",
    )


def generate_response_package(card: dict, support: dict, action: dict, mail_subject: str | None) -> dict:
    config = secret_manager.get_openai_config()
    if not config["api_key"]:
        raise openai_client.OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

    system_prompt = """당신은 글로벌 물류 운영 커뮤니케이션 전문가다.
구조화된 확정 사실과 담당자가 선택한 대응안만 사용하라.
영문 회신은 해외 파트너에게 보내는 간결하고 정중한 비즈니스 메일로 작성한다.
한국어 보고는 임원/팀장이 30초 안에 위험, 변경, 영향, 대응, 확인사항을 파악하도록 작성한다.
제공되지 않은 비용, 납기 보장, 계약 조건은 만들지 마라. 실제 발송 전 담당자 확인을 전제로 한다."""
    payload = {
        "mail_subject": mail_subject,
        "facts": _card_facts(card),
        "ai_risk_analysis": support.get("risk"),
        "impacts": support.get("impacts"),
        "selected_action": action,
    }
    return openai_client.call_structured_json(
        system_prompt,
        json.dumps(payload, ensure_ascii=False, indent=2),
        config,
        schema=RESPONSE_PACKAGE_SCHEMA,
        schema_name="logistics_communication_package",
    )

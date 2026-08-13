"""실제 OpenAI 호출 (Structured Outputs). 서버에서만 호출되며, API
키/엔드포인트는 secret_manager가 넘겨주는 config 인자로만 받는다(이
모듈은 os.environ을 직접 읽지 않는다). 외부 패키지 없이 표준 라이브러리
(urllib)만 사용한다.
"""

import json
import urllib.error
import urllib.request

TIMEOUT_SECONDS = 30

# mock_extract_email_fields와 완전히 동일한 필드 스키마를 모델이 그대로
# 채우도록 강제한다(Structured Outputs). 이 스키마가 바뀌면
# extraction.py의 _empty_fields()/_case()도 함께 맞춰야 한다.
_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "value": {"type": ["string", "null"], "description": "메일 원문에 실제로 적힌 값. 없으면 null."},
        "evidence": {
            "type": ["string", "null"],
            "description": "value가 나온 원문 문장을 그대로 발췌한 것(하이라이트용). value가 null이면 null.",
        },
        "confidence": {
            "type": ["number", "null"],
            "description": "이 추출 결과에 대한 확신도, 0.0~1.0. value가 null이면 null.",
        },
        "extraction_failed": {
            "type": "boolean",
            "description": "이 필드를 메일에서 찾지 못했으면 true (이때 value/evidence/confidence는 모두 null).",
        },
    },
    "required": ["value", "evidence", "confidence", "extraction_failed"],
    "additionalProperties": False,
}

_CASE_FIELD_KEYS = [
    "port_name",
    "call_sign",
    "ship_name",
    "arrival_datetime",
    "next_port",
    "previous_port",
    "ship_id",
    "cargo_volume",
]

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "cases": {
            "type": "array",
            "description": "메일 한 통에서 감지된 선박/일정 변경 건 목록. 여러 선박이 섞여 있으면 건별로 분리한다.",
            "items": {
                "type": "object",
                "properties": {key: _FIELD_SCHEMA for key in _CASE_FIELD_KEYS},
                "required": _CASE_FIELD_KEYS,
                "additionalProperties": False,
            },
        },
    },
    "required": ["cases"],
    "additionalProperties": False,
}


class OpenAIError(Exception):
    pass


def call_structured_extraction(system_prompt: str, user_prompt: str, config: dict) -> dict:
    """Structured Outputs로 {"cases": [...]}를 반환한다. 실패 시 OpenAIError."""
    result = call_structured_json(
        system_prompt,
        user_prompt,
        config,
        schema=RESPONSE_SCHEMA,
        schema_name="mail_change_extraction",
    )
    if not isinstance(result.get("cases"), list):
        raise OpenAIError("OpenAI 응답에 cases 배열이 없습니다.")
    return result


def call_structured_json(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    *,
    schema: dict,
    schema_name: str,
) -> dict:
    """주어진 JSON Schema를 따르는 결과를 반환하는 공용 Structured Output 호출."""
    api_key = config.get("api_key", "")
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

    payload = {
        "model": config.get("model", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema_name,
                "strict": True,
                "schema": schema,
            },
        },
    }
    base_url = config.get("base_url", "https://api.openai.com/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            raw_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise OpenAIError(f"OpenAI 호출 실패(HTTP {exc.code}): {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise OpenAIError(f"OpenAI 연결 실패: {exc.reason}") from exc
    except TimeoutError as exc:
        raise OpenAIError("OpenAI 호출 시간이 초과되었습니다.") from exc

    try:
        parsed = json.loads(raw_body)
        content = parsed["choices"][0]["message"]["content"]
        result = json.loads(content)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise OpenAIError("OpenAI 응답 형식이 올바르지 않습니다.") from exc

    return result

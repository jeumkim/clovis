"""OpenAI 호출 전용 모듈. 서버(백엔드)에서만 호출하며 브라우저에는
API 키가 절대 노출되지 않는다. 외부 패키지 없이 표준 라이브러리
(urllib)만으로 동작한다."""

import json
import os
import urllib.error
import urllib.request

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
TIMEOUT_SECONDS = 20


class OpenAIError(Exception):
    pass


def is_configured():
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def call_openai(system_prompt, user_prompt, model=None):
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

    payload = {
        "model": model or DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=data,
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
        raise OpenAIError(f"OpenAI 호출 실패({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise OpenAIError(f"OpenAI 연결 실패: {exc.reason}") from exc

    try:
        parsed = json.loads(raw_body)
        content = parsed["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise OpenAIError("OpenAI 응답 형식이 올바르지 않습니다.") from exc

    return content

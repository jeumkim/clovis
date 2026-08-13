"""OpenAI 호출 전용 모듈. 서버(백엔드)에서만 호출하며 브라우저에는
API 키가 절대 노출되지 않는다. 외부 패키지 없이 표준 라이브러리
(urllib)만으로 동작한다."""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT_SECONDS = 20
_ENV_PATHS = [
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[1] / "receiver" / ".env",
]
_dotenv_loaded = False


def _load_dotenv_once():
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    for env_path in _ENV_PATHS:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip():
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class OpenAIError(Exception):
    pass


def is_configured():
    _load_dotenv_once()
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def call_openai(system_prompt, user_prompt, model=None):
    _load_dotenv_once()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise OpenAIError("OPENAI_API_KEY가 설정되지 않았습니다.")

    payload = {
        "model": model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
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

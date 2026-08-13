"""사내 Secret Manager를 흉내낸 로컬 설정 로더.

이 파일이 유일하게 OpenAI 관련 설정(API 키, 엔드포인트, 모델명)을
읽는 지점이다. 다른 모듈(extraction.py, openai_client.py)은 절대
os.environ이나 파일을 직접 읽지 않고, 반드시 이 모듈의
get_openai_config()를 통해서만 값을 받는다.

## 프로덕션 전환 방법

실제 배포 환경에서는 get_openai_config()의 구현부만 사내 Secret
Manager(AWS Secrets Manager, HashiCorp Vault, 사내 Vault Proxy 등) SDK
호출로 교체하면 된다. 이 함수를 호출하는 쪽은 반환 딕셔너리 스키마
({"api_key", "base_url", "model"})만 알면 되므로 전혀 수정할 필요가
없다.

## 로컬 개발 환경

.env 파일(커밋되지 않음, .gitignore 등록됨) -> 프로세스 환경변수 순으로
값을 읽는다. 이미 설정된 환경변수가 있으면 .env 값으로 덮어쓰지 않는다
(운영 환경변수가 항상 우선한다). 템플릿은 .env.example을 참고한다.
"""

import os
from pathlib import Path

_MODULE_DIR = Path(__file__).resolve().parent
_ENV_PATHS = [
    _MODULE_DIR.parents[1] / ".env",  # 프로젝트 루트: Sender/Receiver 공용 권장 위치
    _MODULE_DIR / ".env",             # 기존 Receiver 전용 위치도 하위 호환
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
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


def get_openai_config() -> dict:
    """{"api_key": str, "base_url": str, "model": str}를 반환한다.

    실제 Secret Manager 연동 시 이 함수 내부만 교체하면 된다.
    """
    _load_dotenv_once()
    return {
        "api_key": os.environ.get("OPENAI_API_KEY", "").strip(),
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").strip(),
        "model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
    }


def is_ai_configured() -> bool:
    return bool(get_openai_config()["api_key"])


def get_db_path_override() -> str | None:
    """테스트/로컬 개발에서 SQLite 파일 경로를 바꾸고 싶을 때만 사용."""
    _load_dotenv_once()
    value = os.environ.get("RECEIVER_DB_PATH", "").strip()
    return value or None

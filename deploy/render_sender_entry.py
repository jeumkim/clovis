"""Render(클라우드) 배포 전용 실행 스크립트.

backend/sender/server.py는 로컬 실행 스펙(HOST=127.0.0.1, PORT=8765
고정)을 그대로 유지하고, 이 파일은 그 파일의 SenderRequestHandler를
수정 없이 그대로 재사용해서 클라우드 환경(PORT 환경변수, 0.0.0.0
바인딩)에 맞게 띄우기만 한다. backend/ 아래 파일은 전혀 건드리지
않는다.

실행(Render startCommand):
    python deploy/render_sender_entry.py

로컬에서 그대로 실행해도 동작한다(HOST/PORT 환경변수를 안 주면
0.0.0.0:8765로 뜬다. 브라우저에서는 http://127.0.0.1:8765로 접속하면
된다).

접속:
    <서비스 URL>/frontend/index.html
    (backend/sender/server.py의 "/" 리다이렉트는 /frontend/send.html로
    고정되어 있으므로 -- 이 파일에서는 그 코드를 건드리지 않기 위해
    바꾸지 않았다 -- 랜딩 페이지로 바로 가려면 /frontend/index.html
    경로로 접속해야 한다.)
"""

import os
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

_SENDER_DIR = Path(__file__).resolve().parent.parent / "backend" / "sender"
sys.path.insert(0, str(_SENDER_DIR))

# server.py를 모듈로 임포트만 하면(= __main__으로 실행하지 않으면)
# 그 안의 main()은 실행되지 않고, SenderRequestHandler 클래스와
# ROOT_DIR(정적 파일 루트 = 저장소 루트)만 그대로 가져와 쓸 수 있다.
import server as sender_server  # noqa: E402

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8765"))


def main() -> None:
    with ThreadingHTTPServer((HOST, PORT), sender_server.SenderRequestHandler) as httpd:
        print(f"[deploy] Sender 서버 실행 중: {HOST}:{PORT}")
        print(f"[deploy] 정적 파일 루트: {sender_server.ROOT_DIR}")
        print("[deploy] 접속 경로: /frontend/index.html")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[deploy] 서버를 종료합니다.")


if __name__ == "__main__":
    main()

"""Sender(메일 작성) 기능 전용 로컬 서버.

Python 표준 라이브러리만 사용한다(외부 패키지 불필요). 프로젝트 루트를
정적 파일로 제공하면서, /api/sender/ 아래 경로는 자체 API로 처리한다.

실행:
    python backend/sender/server.py

접속:
    http://127.0.0.1:8765/frontend/send.html
"""

import json
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parents[1]  # backend/sender -> backend -> 프로젝트 루트

sys.path.insert(0, str(BASE_DIR))

import ai_generator  # noqa: E402
import openai_client  # noqa: E402
import prompt_builder  # noqa: E402

HOST = "127.0.0.1"
PORT = 8765


class SenderRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT_DIR), **kwargs)

    # ---- 공통 유틸 ----
    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    # ---- 라우팅 ----
    def do_GET(self):
        if self.path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/frontend/send.html")
            self.end_headers()
            return
        if self.path.startswith("/api/sender/"):
            self._route_get()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/sender/"):
            self._route_post()
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "존재하지 않는 경로입니다."})

    def _route_get(self):
        if self.path == "/api/sender/staff/templates":
            self._send_json(HTTPStatus.OK, {"templates": prompt_builder.list_templates()})
            return
        if self.path == "/api/sender/ai-status":
            self._send_json(HTTPStatus.OK, {"available": openai_client.is_configured()})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "존재하지 않는 API 경로입니다."})

    def _route_post(self):
        try:
            payload = self._read_json_body()
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "잘못된 요청 형식입니다."})
            return

        if self.path == "/api/sender/staff/compose-request":
            self._handle_compose_request(payload)
            return
        if self.path == "/api/sender/staff/generate":
            self._handle_generate(payload)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "존재하지 않는 API 경로입니다."})

    def _handle_compose_request(self, payload):
        template_id = payload.get("template_id", "")
        values = payload.get("values", {}) or {}
        try:
            result = prompt_builder.build_compose_request(template_id, values)
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, result)

    def _handle_generate(self, payload):
        template_id = payload.get("template_id", "")
        values = payload.get("values", {}) or {}
        importance_override = payload.get("importance_override")

        result = ai_generator.generate(template_id, values, importance_override=importance_override)
        status = HTTPStatus.OK if result.get("ok") else HTTPStatus.BAD_REQUEST
        self._send_json(status, result)

    def log_message(self, fmt, *args):
        sys.stderr.write("[sender] " + (fmt % args) + "\n")


def main():
    with ThreadingHTTPServer((HOST, PORT), SenderRequestHandler) as httpd:
        print(f"Sender 로컬 서버 실행 중: http://{HOST}:{PORT}/frontend/send.html")
        print(f"정적 파일 루트: {ROOT_DIR}")
        print(f"OpenAI 연동: {'사용 가능' if openai_client.is_configured() else '미설정 (표준 미리보기만 사용)'}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nSender 로컬 서버를 종료합니다.")


if __name__ == "__main__":
    main()

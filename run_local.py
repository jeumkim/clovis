"""저장소 전체(Receiver + Sender)를 한 번에 띄우고 브라우저를 여는
로컬 실행 스크립트.

사용법:
    python run_local.py

무엇을 하는가:
    1. backend/receiver를 FastAPI(uvicorn)로 http://127.0.0.1:8766 에 띄운다.
    2. backend/sender/server.py를 http://127.0.0.1:8765 에 띄운다.
       이 서버는 API뿐 아니라 저장소 전체를 정적 파일로도 함께 제공하므로
       frontend/ 전용 서버를 따로 띄울 필요가 없다 — index.html/
       receive.html/send.html 모두 이 서버 하나로 열람 가능하다.
    3. 두 서버가 응답할 때까지 기다린 뒤 첫 페이지
       (http://127.0.0.1:8765/frontend/index.html)를 기본 브라우저로 연다.
       거기서 "메일 수신 처리"/"메일 발신 작성" 링크를 눌러 각 화면으로
       이동하면 된다.
    4. 이 창에서 Ctrl+C를 누르면 두 서버가 함께 종료된다.

사전 준비:
    backend/receiver/requirements.txt가 설치되어 있어야 한다.
        pip install -r backend/receiver/requirements.txt
    backend/sender는 표준 라이브러리만 사용하므로 별도 설치가 필요 없다.
"""

import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RECEIVER_DIR = ROOT / "backend" / "receiver"
SENDER_SERVER = ROOT / "backend" / "sender" / "server.py"

RECEIVER_URL = "http://127.0.0.1:8766"
SENDER_URL = "http://127.0.0.1:8765"
START_PAGE = f"{SENDER_URL}/frontend/index.html"


def wait_until_up(url, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            time.sleep(0.3)
    return False


def main():
    print("Receiver(8766), Sender(8765) 서버를 시작합니다...\n")

    procs = []
    try:
        receiver_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8766"],
            cwd=str(RECEIVER_DIR),
        )
        procs.append(("receiver", receiver_proc))

        sender_proc = subprocess.Popen(
            [sys.executable, str(SENDER_SERVER)],
            cwd=str(ROOT),
        )
        procs.append(("sender", sender_proc))

        receiver_ok = wait_until_up(f"{RECEIVER_URL}/health")
        sender_ok = wait_until_up(f"{SENDER_URL}/api/sender/ai-status")

        if not receiver_ok:
            print(
                "! Receiver 서버(8766)가 응답하지 않습니다. "
                "backend/receiver/requirements.txt가 설치되어 있는지 확인하세요:\n"
                "    pip install -r backend/receiver/requirements.txt\n"
            )
        if not sender_ok:
            print("! Sender 서버(8765)가 응답하지 않습니다.\n")

        if receiver_ok and sender_ok:
            print(f"준비 완료. 브라우저를 엽니다: {START_PAGE}\n")
            webbrowser.open(START_PAGE)
        else:
            print("일부 서버가 정상 기동되지 않았습니다. 위 메시지와 아래 서버 로그를 확인하세요.\n")

        print("종료하려면 이 창에서 Ctrl+C를 누르세요.\n")

        while True:
            time.sleep(1)
            for name, p in procs:
                if p.poll() is not None:
                    print(f"\n[{name}] 프로세스가 예기치 않게 종료되었습니다(exit code {p.returncode}).")
                    raise KeyboardInterrupt

    except KeyboardInterrupt:
        print("\n서버를 종료합니다...")
    finally:
        for _, p in procs:
            if p.poll() is None:
                p.terminate()
        for _, p in procs:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        print("종료되었습니다.")


if __name__ == "__main__":
    main()

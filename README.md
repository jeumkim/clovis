# clovis — 메일 업무 자동화 서비스

선박 운영 관련 메일 업무(발송/수신)를 AI로 자동화하는 서비스입니다.
발송 자동화(Sender), 수신 자동화(Receiver), 프론트(Frontend) 세 파트가
서로 다른 사람이 동시에 작업해도 파일이 충돌하지 않도록 폴더가
모듈화되어 있습니다.

## 3파트 역할

1. **발송 자동화 (Sender)** — 사용자가 정해진 체크 항목(비용 집계, 물건
   상태값 등 매일 반복되는 단순 보고 사항)을 입력하면, AI가 이를 메일
   형식 문장으로 작성해줍니다.
2. **수신 자동화 (Receiver)** — 수신 메일 중 변경 사항 관련 메일의 내용을
   AI가 요약·추출하여 기존 DB(선박 일정/화물량 등)와 대조하고, 변경된
   사항을 선박 ID 기준으로 사용자에게 알립니다.
3. **프론트 (Frontend)** — 첫 페이지에서 "메일 수신 처리" / "메일 발신
   작성" 중 하나를 선택하면 각각 수신 전용 페이지, 발신 전용 페이지로
   이동합니다. 두 페이지는 별도 파일(`receive.html` / `send.html`)로
   분리되어 있어 Sender/Receiver와 무관하게 화면만 독립적으로 수정할 수
   있습니다.

## 담당 폴더 — "이 폴더만 수정하면 됩니다"

| 파트 | 폴더 | 비고 |
| --- | --- | --- |
| 발송 자동화 (Sender) | [`backend/sender/`](backend/sender/) | 다른 파트는 이 폴더를 수정하지 않습니다 |
| 수신 자동화 (Receiver) | [`backend/receiver/`](backend/receiver/) | 다른 파트는 이 폴더를 수정하지 않습니다 |
| 프론트 (Frontend) | [`frontend/`](frontend/) | 다른 파트는 이 폴더를 수정하지 않습니다 |
| 공용 | [`common/`](common/) | 세 파트가 공유하는 유틸/타입만. 임의로 늘리지 않습니다 |

즉, receiver 파트 담당자는 `backend/receiver/` 폴더만 건드리면 되고, sender
파트 담당자는 `backend/sender/`만, frontend 담당자는 `frontend/`만 건드리면
됩니다.

## 폴더 구조

```
clovis/
├── backend/
│   ├── sender/     # 발송 자동화 전용. server.py가 API(8765)와
│   │                 frontend/ 정적 파일을 함께 제공한다
│   └── receiver/   # 수신 자동화 전용 API (포트 8766)
├── frontend/       # 화면 전용 (별도 서버 없이 backend/sender/server.py가 함께 제공)
│   ├── index.html    # 첫 페이지 (수신/발신 선택)
│   ├── receive.html  # 수신 전용 화면
│   └── send.html     # 발신 전용 화면
├── common/         # 세 파트 공유 유틸/타입 (있는 경우만)
├── run_local.py    # 두 백엔드를 한 번에 띄우고 첫 페이지를 여는 실행 스크립트
├── run_local.bat   # 위 스크립트를 더블클릭으로 실행하는 Windows용 래퍼
└── README.md
```

## 로컬 실행 방법

### 가장 쉬운 방법: 한 번에 실행

두 백엔드를 각자 따로 띄울 필요 없이, 저장소 루트에서 아래 하나만
실행하면 된다.

```bash
python run_local.py
```

(Windows에서는 `run_local.bat`을 더블클릭해도 된다.)

- Receiver(8766)와 Sender(8765)를 함께 띄운다. Sender 서버가 저장소
  전체를 정적 파일로도 제공하므로 `frontend/` 전용 서버는 따로 필요
  없다.
- 두 서버가 응답하면 첫 페이지(`http://127.0.0.1:8765/frontend/index.html`)
  를 기본 브라우저로 자동으로 연다. 거기서 "메일 수신 처리" /
  "메일 발신 작성" 링크를 누르면 각 화면으로 이동하며, 두 화면 모두
  바로 동작한다(별도로 다른 서버를 추가로 켤 필요가 없다).
- 사전에 `pip install -r backend/receiver/requirements.txt`가 되어
  있어야 한다(Sender는 표준 라이브러리만 사용).
- 종료하려면 스크립트를 실행한 창에서 `Ctrl+C`를 누른다. 두 서버가
  함께 종료된다.

### 수동 실행 (각 파트를 따로 띄우고 싶을 때)

| 파트 | 실행 위치 | 명령어 | 접속 |
| --- | --- | --- | --- |
| Sender (+ frontend 정적 파일) | 저장소 루트 | `python backend/sender/server.py` | `http://127.0.0.1:8765/frontend/index.html` |
| Receiver | `backend/receiver/` | `pip install -r requirements.txt && uvicorn main:app --reload --port 8766` | `http://127.0.0.1:8766/health` |

Sender 서버 하나만으로 `index.html`/`receive.html`/`send.html`이 모두
열람 가능하지만, `receive.html`의 기능이 동작하려면 Receiver도 함께
떠 있어야 한다(반대로 `send.html`은 Sender 서버 하나로 완결된다).

세부 실행 방법과 담당 범위는 각 폴더의 README.md를 참고하세요.

## 개발 로드맵

1. **Receiver MVP** — 수신 메일 요약·추출 및 DB 대조 기본 동작 구현
2. **Sender** — 체크 항목 입력 → AI 메일 문장 생성 기본 동작 구현
3. **Receiver 고도화** — 정확도 개선, 예외 케이스 처리, 알림 개선
4. **아키텍처 전환** — 서비스 규모에 맞춘 구조 개편 (예: 배포/인프라 정리)

## 공유 파일 수정 규칙

이 README, `common/`, 루트 설정 파일 등 여러 파트가 함께 의존하는 파일을
수정할 때는 반드시 PR 리뷰를 거쳐 머지합니다.
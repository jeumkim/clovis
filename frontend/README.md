# frontend — 화면

첫 페이지(`index.html`)에서 "메일 수신 처리" / "메일 발신 작성" 중 하나를
선택하면 각각 `receive.html`, `send.html`로 이동합니다.

이 폴더는 Frontend 파트 담당자만 수정합니다. 다른 파트는 이 폴더를 수정하지
않습니다.

## 가장 쉬운 실행 방법

저장소 루트에서 `python run_local.py`(또는 Windows에서 `run_local.bat`
더블클릭)를 실행하면 Receiver/Sender 백엔드가 함께 뜨고
`http://127.0.0.1:8765/frontend/index.html`이 자동으로 열린다. 거기서
두 화면 모두 바로 동작한다. 자세한 내용은 [루트 README](../README.md)의
"로컬 실행 방법" 참고.

아래 내용은 각 화면을 개별적으로 띄우고 싶을 때를 위한 세부 설명이다.

## 파일 구성

| 파일 | 역할 |
| --- | --- |
| `index.html` | 첫 페이지. 수신/발신 선택 |
| `receive.html` | 수신 정식 화면. 메일 처리(선택→검토→업데이트 확인)와 우선순위 대시보드 탭 |
| `send.html` | 발신 전용 화면. 정형화된 메일 작성 기능(메일 회신/업무보고 등 7종) 동작 |
| `legacy/receiver-draft.html` | **deprecated.** 아래 "legacy/" 단락 참고 |
| `app.css` | `send.html` 전용 스타일 (현대글로비스 CI 남색 기반) |
| `style.css` | 공통 스타일 (`index.html`, `receive.html`용) |
| `assets/` | `send.html` 헤더용 브랜드 이미지 위치. [assets/README.md](assets/README.md) 참고 |

## Sender 화면 (`send.html`) 실행

`send.html`은 backend/sender의 정형화된 메일 작성 API와 함께 동작한다.
API 서버와 정적 파일을 함께 제공하는 `backend/sender/server.py`(Python
표준 라이브러리만 사용, 외부 패키지 설치 불필요)를 실행한 뒤 접속한다.

```bash
python backend/sender/server.py
```

접속: `http://127.0.0.1:8765/frontend/send.html`

(이 화면은 `python -m http.server 5500`가 아니라 `backend/sender/server.py`로
열어야 한다. server.py가 `/api/sender/` API와 정적 파일을 같은 주소에서
함께 제공하기 때문이다.)

`receive.html`과 `send.html`은 별도 파일로 분리되어 있어, 한쪽 화면을
수정해도 다른 화면과 충돌하지 않습니다.

## Receiver 정식 화면 (`receive.html`)

Receiver MVP 단계(모든 기능을 한 페이지에 욱여넣은 통합 초안)를 거쳐,
지금은 backend/receiver 고도화(SQLite 감사 이력, 건별 승인/반려,
Structured Outputs 등) 결과를 반영한 정식 화면입니다.

- 탭 1 "메일 처리": 메일 선택(예시 불러오기 또는 원문 붙여넣기) →
  `POST /api/receiver/extract`로 추출 → `POST /api/receiver/compare`로
  검토 카드(캘린더 3-way 비교, 변경 필드 하이라이트, 근거 문장·확신도,
  DB 미등록/이상값 경고 배지) → 카드별 "승인"/"반려" 버튼까지 한 화면
  흐름으로 확인합니다. 실제 메일함 연동은 하지 않으며(사유는
  `backend/receiver/mail_source.py` 상단 주석 참고), "예시 불러오기"
  버튼으로 준비된 mock 시나리오 3건(입항일 변경 단건 / 화물량 변경
  단건 / 복합 변경 다건)을 그대로 붙여넣은 것처럼 불러올 수 있습니다.
  AI 연동이 설정되어 있는데 호출이 실패하면(예: 잘못된 키) 카드 대신
  "AI 추출 실패 - 수동 확인 필요" 배너가 뜨고, mock으로 자동
  대체되지 않습니다.
- 탭 2 "우선순위 대시보드": 아직 승인/반려되지 않은 건만 모아 우선순위
  점수 순으로 정렬해 보여줍니다. 정렬 기준(우선순위/일정 변경폭/화물량
  변경률/입항 임박순)은 화면에서 바꿀 수 있습니다. 승인/반려된 건은
  자동으로 목록에서 빠집니다.
- 탭 3 "변경 이력": 승인/반려 이력을 감사 추적용으로 보여줍니다
  (시각/처리자/선박/승인·반려 여부/변경 내용/메일 근거). SQLite
  `change_history` 테이블을 그대로 조회하며, 이 표는 항상
  append-only입니다.
- "승인" 버튼은 SQLite `ships` 테이블에 실제로 반영됩니다(클릭 시
  브라우저 콘솔에도 로그가 남습니다). "반려"는 이력에만 기록되고 DB는
  바뀌지 않습니다. DB에 등록되지 않은 선박은 승인 버튼이 비활성화됩니다.
  이미 승인/반려된 건은 다시 열어도 잠긴 상태로 표시됩니다.
- 사용법: backend/receiver를 `uvicorn main:app --reload --port 8766`로
  띄운 뒤, `receive.html`을 아무 정적 서버로든 열면 된다(`receive.html`은
  Receiver API를 절대 주소 `http://localhost:8766`으로 직접 호출하므로,
  자신을 서빙하는 서버가 무엇이든 상관없다). 예: `python -m
  http.server 5500` 또는 `backend/sender/server.py`(둘 다 됨).

## legacy/

`legacy/receiver-draft.html`은 Receiver MVP 단계의 통합 초안으로,
**더 이상 동작하지 않습니다**(당시 API가 이후 `/mail/process`를 거쳐
지금은 `/api/receiver/*`(8766번 포트, SQLite 기반)로 대체됨). 과거
참고용으로만 보존합니다. 자세한 내용은 파일 상단 주석을 참고하세요.

## 개별 정적 서버로 열람만 하고 싶을 때

```bash
cd frontend
python -m http.server 5500
```

- 접속: `http://localhost:5500/index.html`
- `index.html`, `receive.html`은 이 방식으로도 정상 동작한다(각자 백엔드를
  절대 주소로 직접 호출하기 때문). 단, `send.html`은 `/api/sender/...`를
  **같은 origin의 상대 경로**로 호출하므로, 이 방식(5500번 정적 서버)으로
  열면 API 호출이 실패한다 — `send.html`은 반드시
  `backend/sender/server.py`(8765번)로 열어야 한다.
- 즉 세 화면을 모두 정상 동작시키려면 위 "가장 쉬운 실행 방법"
  (`run_local.py`)을 쓰거나, `backend/sender/server.py` 하나로
  `index.html`/`receive.html`/`send.html`을 모두 열람하는 편이 낫다
  (Receiver 화면 기능은 별도로 Receiver 서버도 떠 있어야 한다).

(VSCode Live Server 등 다른 정적 서버를 사용해도 무방합니다.)

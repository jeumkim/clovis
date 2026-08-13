# backend/sender — 발송 자동화

사용자가 입력한 체크 항목(비용 집계, 물건 상태값 등 매일 반복되는 단순 보고
사항)을 AI가 메일 형식 문장으로 작성해주는 서비스입니다.

이 폴더는 Sender 파트 담당자만 수정합니다. 다른 파트는 이 폴더를 수정하지
않습니다.

> Receiver까지 함께 띄워 전체 서비스를 한 번에 켜고 싶다면 저장소
> 루트의 `python run_local.py`를 대신 실행하세요.

## 로컬 실행 (정형화된 메일 작성 기능)

`server.py`는 외부 패키지 없이 Python 표준 라이브러리만으로 동작하는
로컬 서버다. 프로젝트 루트를 정적 파일로 제공하면서 `/api/sender/`
아래 경로를 자체 API로 처리하므로, 별도 설치 없이 바로 실행할 수 있다.

```bash
python backend/sender/server.py
```

- 기본 주소: `http://127.0.0.1:8765`
- 메일 작성 화면: `http://127.0.0.1:8765/frontend/send.html`
- `OPENAI_API_KEY` 환경변수가 설정되어 있으면 실제 자동 작성(OpenAI)을
  시도하고, 없거나 호출에 실패하면 항상 표준 미리보기로 대체한다.

`main.py`(FastAPI, 8001번 포트)는 기존 골격을 그대로 유지한다. 이번
기능은 `server.py`를 통해 별도로 제공된다.

## 담당 범위

- 체크 항목 입력 처리
- AI 메일 문장 생성 로직
- Sender 관련 API 엔드포인트

`common/`에 있는 공유 유틸/타입 외의 파일은 이 폴더 안에서만 추가·수정합니다.

## 폴더 구성 (정형화된 메일 작성 기능)

```
backend/sender/
├── server.py               # 표준 라이브러리 기반 로컬 서버 (127.0.0.1:8765)
├── staff_templates.json     # 업무 유형 7종 필드 정의
├── prompt_builder.py         # 입력값 정리 + 상세 작성 요청(compose-request) 생성
├── staff_mail_generator.py   # OpenAI 없이도 동작하는 표준 미리보기 생성기
├── openai_client.py          # OpenAI 호출 (urllib만 사용, 서버에서만 호출)
├── ai_generator.py           # AI/표준 미리보기 분기, 중요도 판정, 검증
├── PROMPT.md                 # 공통 작성 원칙 (시스템 프롬프트 기반 텍스트)
└── STAFF_PROMPT.md           # 업무 유형별 추가 작성 규칙
```

## API

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/api/sender/staff/templates` | 업무 유형 7종 필드 정의 |
| GET | `/api/sender/ai-status` | 자동 작성 연동(OpenAI) 사용 가능 여부 |
| POST | `/api/sender/staff/compose-request` | 선택한 업무 유형+입력값으로 상세 작성 요청 생성 |
| POST | `/api/sender/staff/generate` | 메일 제목/본문 생성 (자동 작성 또는 표준 미리보기), 중요도·검증 결과 포함 |

## 메일 작성 원칙

입력에 없는 수치·날짜·원인·담당자·기한·사실을 추론하지 않고, 필드명과
값을 그대로 나열하지 않으며, 격식 있는 문장으로 정리한다. 자세한
원칙은 [PROMPT.md](./PROMPT.md), 업무 유형별 규칙은
[STAFF_PROMPT.md](./STAFF_PROMPT.md)를 참고한다.

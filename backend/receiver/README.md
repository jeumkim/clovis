# backend/receiver — 수신 자동화

수신 메일 중 변경 사항 관련 메일의 내용을 AI가 요약·추출하여 기존
DB(선박 일정/화물량 등)와 대조하고, 변경된 사항을 검토·승인/반려할 수
있게 하는 서비스입니다.

이 폴더는 Receiver 파트 담당자만 수정합니다. 다른 파트는 이 폴더를 수정하지
않습니다.

> Sender까지 함께 띄워 전체 서비스를 한 번에 켜고 싶다면 저장소
> 루트의 `python run_local.py`를 대신 실행하세요.

## 로컬 실행

```bash
cd backend/receiver
pip install -r requirements.txt
cp .env.example .env   # 필요 시 OPENAI_API_KEY 등을 채운다. 비워두면 mock 경로로 동작한다.
uvicorn main:app --reload --port 8766
```

- 기본 포트: `8766` (backend/sender의 8765/127.0.0.1:8765와 겹치지 않도록 분리)
- 헬스체크: `GET http://localhost:8766/health`
- 최초 기동 시 SQLite DB(`data/receiver.db`, gitignore됨)가 없으면 자동으로
  테이블을 만들고 `data/ships_seed.json`으로 시드한다.

## 담당 범위

- 수신 메일 파싱 및 AI 요약·추출
- 기존 DB(선박 일정/화물량 등)와의 대조 로직
- 변경 건 승인/반려 및 감사 이력 관리

`common/`에 있는 공유 유틸/타입 외의 파일은 이 폴더 안에서만 추가·수정합니다.

## 폴더 구성

```
backend/receiver/
├── main.py               # FastAPI 엔드포인트 (/api/receiver/*)
├── secret_manager.py       # OpenAI 설정(.env/환경변수) 로더 — 사내 Secret Manager 대역
├── .env.example             # 로컬 개발용 설정 템플릿 (실제 .env는 커밋하지 않음)
├── mail_source.py            # 처리 대상 메일 진입점 (source="paste"|"inbox")
├── columns.py                # PORT-MIS_HPNT_raw.xlsx 기준 목표 컬럼 정의
├── extraction.py              # mock_extract_email_fields(로컬 테스트/폴백) + extract_email_fields(실 연동)
├── openai_client.py            # 실제 OpenAI 호출 (Structured Outputs, urllib만 사용)
├── PROMPT.md                    # 실 연동 시스템 프롬프트 (문구 수정은 이 파일에서)
├── db.py                        # SQLite: ships(마스터) + change_history(append-only 감사 이력)
├── highlight.py                  # 추출값 vs DB값 필드별 대조(변경/동일/누락/DB없음 상태 판정)
├── validation.py                 # 표기 정규화(숫자/날짜) + 이상값 검증(과거 날짜, 적재량 초과)
├── calendar_view.py               # 오늘/기존/변경 3-way 캘린더 격자 데이터 생성
├── priority.py                    # 변경폭+긴급도+예외 기반 우선순위 점수, 정렬
├── review.py                      # 위 모듈들을 한 건(case) 단위로 조립해 검토 카드로 반환
├── scenarios/                      # 수신 메일 시나리오 (분류는 이미 끝났다고 가정)
│   ├── scenario_eta_change.json       # 입항일 변경, 단건
│   ├── scenario_cargo_change.json     # 화물량 변경, 단건
│   └── scenario_combined_change.json  # 다건(선박 3척)이 한 메일에 섞인 경우
└── data/
    ├── ships_seed.json      # SQLite 최초 시드 데이터 (max_cargo_capacity 포함)
    └── receiver.db          # 런타임 SQLite 파일 (gitignore, 자동 생성됨)
```

## 전제

메일 분류(어떤 메일이 "일정/화물량 변경 문의"인지 판별하는 작업)는 이미
선행되었다고 가정한다. 이 폴더는 그 분류 결과로 넘어온 메일만 다룬다.

## 1. OpenAI 키 관리 (Secret Manager 분리)

API 키/엔드포인트/모델명은 코드에 없다. `secret_manager.py`의
`get_openai_config()`가 유일한 조회 지점이며, 다른 모든 모듈은 이
함수를 통해서만 값을 받는다.

- 로컬 개발: `.env` 파일(커밋 안 됨, `.gitignore` 등록) → 환경변수 순으로
  읽는다. 템플릿은 `.env.example`.
- 프로덕션 전환: `get_openai_config()` 내부만 사내 Secret Manager SDK
  호출로 교체하면 된다. 호출하는 쪽은 반환 스키마만 알면 되므로 다른
  코드는 수정할 필요가 없다.

**확인 방법**: `git grep -n "OPENAI_API_KEY" backend/receiver` 를 실행하면
`secret_manager.py`와 `.env.example` 외에는 나오지 않는다. `.env`는
`git status`에 잡히지 않는다(`.gitignore`).

## 2. mock 경로 = 로컬 테스트 겸 폴백 (계속 유지)

`mock_extract_email_fields` / `unrecognized_case`는 "API 연동 전
임시 코드"가 아니라 정식으로 유지되는 경로다.

- API 키가 아예 설정되지 않은 경우, `extraction.extract_cases()`가
  자동으로 이 경로를 쓴다(`mode: "mock"`). 이는 정상 상태이며, 이
  경로만으로 추출→대조→검토→우선순위 대시보드 전체 흐름을 점검할 수
  있다.
- API 키가 설정되어 있는데 실제 호출이 실패한 경우에는 **이 경로로
  자동 대체하지 않는다.** 이 경우는 `mode: "error"`로 명확히 구분된다
  (9번 항목 참고).

**확인 방법**: `.env`를 비워두고(또는 `OPENAI_API_KEY` 미설정) 서버를
띄운 뒤 `POST /api/receiver/extract`를 호출하면 `mode: "mock"`이 온다.

## 3. 누락 필드 = null + extraction_failed 플래그

각 추출 필드는 `{"value", "evidence", "confidence", "extraction_failed"}`
스키마를 가진다. 메일에서 찾지 못한 필드는 `value/evidence/confidence`가
모두 `null`이고 `extraction_failed: true`다 — 절대 임의 값으로 채우지
않는다. `highlight.py`가 이 플래그를 보고 `status: "missing"`을
매긴다(프론트에서 "추출 실패"로 표시).

**확인 방법**: `scenario_eta_change` 메일은 화물량을 언급하지 않으므로
추출 결과의 `cargo_volume.extraction_failed`가 `true`, `value`는
`null`이다.

## 4. 죽은 코드 정리

리팩터링 과정에서 이전 버전의 `/mail/process`, `/priority-dashboard`,
`/update` 엔드포인트와 그 전용 Pydantic 모델(`ProcessMailRequest`,
`UpdateRequest`), JSON 파일 기반 `db.load_ships_db()`를 모두
`/api/receiver/*` 신규 엔드포인트와 SQLite 기반 `db.py`로 교체하며
제거했다. 교체 후 전체 모듈에 대해 정의된 함수/상수/임포트가 실제로
참조되는지 grep으로 전수 확인했고, 사용되지 않는 정의나 임포트는
남아있지 않다(FastAPI 라우트 핸들러처럼 프레임워크가 호출하는 함수는
제외).

**확인 방법**: `git grep -n "def \|^import \|^from " backend/receiver/*.py`
로 정의 목록을 뽑고, 각 이름을 `git grep`으로 재검색하면 자기 자신의
정의 줄 외에 최소 1곳에서 더 참조됨을 확인할 수 있다.

## 5. 실제 연동: Structured Outputs

`openai_client.call_structured_extraction()`이 OpenAI Chat Completions
API를 `response_format: {"type": "json_schema", ...}` (Structured
Outputs)로 호출해, 모델이 `{"cases": [...]}` 를 mock과 완전히 동일한
필드 스키마(`value`/`evidence`/`confidence`/`extraction_failed`)로
직접 반환하도록 강제한다. 시스템 프롬프트는 `PROMPT.md`.

이 스키마가 mock과 동일하므로 `extraction.extract_cases()`는 내부
분기(`mode`)만 바꿀 뿐, 이후 파이프라인(`highlight.py`, `review.py`
등)은 mock/실제 연동을 구분하지 않는다.

**확인 방법**: `.env`에 유효한 `OPENAI_API_KEY`를 넣고 서버를 띄운 뒤
`POST /api/receiver/extract`를 호출하면 `mode: "openai"`가 오고, 반환된
`cases[].fields`가 mock과 동일한 키 구조를 가진다.

## 6. 다중 변경 건 배열 + 건별 승인/반려

`scenario_combined_change`처럼 한 메일에 여러 선박/건이 섞여 있으면
`cases` 배열로 분리되어 온다. `frontend/receive.html`은 케이스별로 카드를
만들고, 카드마다 독립된 "승인"/"반려" 버튼을 제공한다. 승인은 SQLite
`ships` 테이블에 반영되고, 반려는 이력에만 남고 DB는 바뀌지 않는다. 이미
결정된 건은 재조회 시 `decision` 필드로 표시되며 버튼이 잠긴다.

**확인 방법**: `receive.html`에서 "복합 변경 문의 (다건)" 예시를 불러와
분석하면 카드 3개가 나온다. 하나를 반려하고 다시 같은 예시를 분석하면
그 카드는 "이미 반려됨"으로 잠겨 있고, 우선순위 대시보드에서는 빠져
있다.

## 7. SQLite 전환 + 감사 이력

`db.py`가 JSON 파일 대신 SQLite(`data/receiver.db`)를 쓴다.

- `ships` 테이블: 선박 마스터 데이터. `apply_approved_changes()`만
  이 표를 `UPDATE`한다(승인된 필드만, 승인 시에만).
- `change_history` 테이블: `(id, case_id, ship_call_sign, action,
  changed_at, changed_by, mail_reference, changes_json)`. **append-only**
  — 코드 전체에서 이 표에 `UPDATE`/`DELETE`를 실행하는 곳은 없다.
  `record_history()`가 매번 새 행을 `INSERT`할 뿐이다.

최초 기동 시 `ships`가 비어 있으면 `data/ships_seed.json`으로 시드한다.
테스트/로컬 격리가 필요하면 `.env`의 `RECEIVER_DB_PATH`로 DB 파일
경로를 바꿀 수 있다.

**확인 방법**: 카드를 하나 승인한 뒤 `GET /api/receiver/history`(또는
"변경 이력" 탭)를 보면 `action: "approved"` 행이 추가돼 있고,
`sqlite3 data/receiver.db "select * from ships"`로 실제 값이 바뀐 것을
확인할 수 있다. 반려는 `change_history`에만 행이 추가되고 `ships`는
그대로다.

## 8. FastAPI 엔드포인트 (127.0.0.1:8766)

Sender(`backend/sender/server.py`, 127.0.0.1:8765)와 포트가 겹치지
않도록 Receiver는 `8766`을 쓴다.

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| GET | `/health` | 헬스체크 |
| GET | `/columns` | PORT-MIS 목표 컬럼 전체 정의 |
| GET | `/scenarios` | 시나리오 목록 (프론트 "예시 불러오기"용) |
| GET | `/scenarios/{id}` | 시나리오 메일 원문 |
| POST | `/api/receiver/extract` | 메일 원문 → 추출 결과 (`mode`: mock\|openai\|error) |
| POST | `/api/receiver/compare` | 추출 결과(`/extract`의 `cases`) → DB 대조 + 하이라이트 + 캘린더 + 경고 + 우선순위 |
| POST | `/api/receiver/approve` | 변경 건 승인 → SQLite `ships` 반영 + `change_history` 기록 |
| POST | `/api/receiver/reject` | 변경 건 반려 → `change_history`만 기록, DB는 변경 없음 |
| GET | `/api/receiver/dashboard?sort=` | 아직 승인/반려되지 않은 건을 우선순위 순 정렬 (`sort`: priority\|schedule_days\|cargo_percent\|urgency) |
| GET | `/api/receiver/history?limit=` | 감사 이력 조회(검증용 보조 엔드포인트) |

`/extract` → `/compare`는 의도적으로 분리되어 있다: `/extract`가 반환한
`cases` 배열을 그대로 `/compare`에 넘기면 된다(각각 독립적으로 curl로
검증 가능).

## 9. 오류 상태 명시 (AI 추출 실패)

`extraction.extract_cases()`는 세 가지 `mode`만 반환한다.

- `"mock"`: 키가 없어서 로컬 테스트 경로 사용(정상, 에러 아님).
- `"openai"`: 실제 호출 성공.
- `"error"`: 키는 있는데 호출이 실패함(잘못된 키, 네트워크 오류, 응답
  파싱 실패 등). **이때 mock으로 자동 대체하지 않는다** —
  `cases: []`와 사람이 읽을 수 있는 `error` 메시지를 그대로 반환한다.

서버는 `logger.error("AI 추출 실패 (scenario_id=...): ...")`로 원인을
남기고, `frontend/receive.html`은 이 경우 카드 대신
"⚠ AI 추출 실패 - 수동 확인 필요" 배너와 오류 상세를 그대로 노출한다.

**확인 방법**: `.env`의 `OPENAI_API_KEY`에 일부러 잘못된 값(예:
`sk-invalid-000`)을 넣고 서버를 띄운 뒤 `receive.html`에서 아무 예시나
분석을 시작하면, 카드 대신 위 배너가 뜨고 서버 콘솔에
`ERROR:clovis.receiver.extraction:AI 추출 실패 ...` 로그가 남는다.

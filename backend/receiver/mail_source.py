"""처리 대상 메일을 가져오는 단일 진입점.

## 실제 메일함(Outlook/Gmail 등) 연동 검토 결과

이번 단계에서는 다루지 않는다.

- OAuth 앱 등록/승인, 회사 메일 서버(Exchange Online, Google Workspace)
  관리자 권한이 선행되어야 하며, 로컬 mock 개발 환경에서 준비하기 어렵다.
- 수신함 읽기 권한 자체가 보안 검토 대상이라 별도 승인 절차가 필요하다.
- 애초에 "어떤 메일이 처리 대상인지 판별"하는 메일 분류 단계 자체가 아직
  mock이므로, 실제 수신함 연동을 지금 붙이는 것은 우선순위가 낮다.

그래서 이번 단계는 "메일 원문 붙여넣기"로 구현하고, 나중에 실제 수신함
연동을 붙일 때는 아래 get_target_email의 source="inbox" 분기만 채우면
되도록 분리해 두었다. 호출하는 쪽(main.py)은 수정할 필요가 없다.
"""

import json
from pathlib import Path

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


class MailSourceError(Exception):
    pass


def _load_scenario_file(scenario_id):
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise MailSourceError(f"시나리오를 찾을 수 없습니다: {scenario_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def get_target_email(source="paste", *, scenario_id=None, raw_text=None, subject=None):
    """처리 대상 메일 1건을 반환한다.

    반환 스키마(모든 source 공통): {scenario_id, subject, body, from, received_at}

    source="paste": 사용자가 화면에 붙여넣은 원문을 그대로 사용한다.
        scenario_id가 함께 주어지면(화면의 "예시 불러오기" 버튼으로 채운
        경우) 저장된 시나리오 메일 원문을 그대로 반환해 mock 추출과
        1:1로 대응시킨다. scenario_id 없이 raw_text만 주어지면 사용자가
        직접 붙여넣은 임의의 원문이므로, 값을 지어내지 않고 그대로
        내려보낸다(추출 단계에서 "인식되지 않은 메일"로 처리된다).

    source="inbox": 아직 구현하지 않았다. 실제 연동 시 이 분기만 채우면
        나머지 파이프라인(추출/대조/검토 화면)은 그대로 재사용할 수 있다.
    """
    if source == "inbox":
        raise NotImplementedError(
            "실제 메일함(Outlook/Gmail 등) 연동은 아직 구현되지 않았습니다. "
            "source='paste'로 원문을 붙여넣어 사용하세요."
        )
    if source != "paste":
        raise MailSourceError(f"지원하지 않는 source입니다: {source}")

    if scenario_id:
        scenario = _load_scenario_file(scenario_id)
        return {
            "scenario_id": scenario["id"],
            "subject": scenario["mail"]["subject"],
            "body": scenario["mail"]["body"],
            "from": scenario["mail"].get("from"),
            "received_at": scenario["mail"].get("received_at"),
        }

    if not raw_text or not raw_text.strip():
        raise MailSourceError("붙여넣은 메일 원문이 없습니다.")
    return {
        "scenario_id": None,
        "subject": (subject or "").strip(),
        "body": raw_text,
        "from": None,
        "received_at": None,
    }

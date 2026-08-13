"""업무 유형 템플릿을 읽고, 사용자가 입력한 값으로 "상세 작성 요청"을 만든다.

여기서 만드는 상세 작성 요청은 화면의 "메일 작성 기준" 패널에 그대로
보여줄 수 있고, ai_generator가 실제 메일 생성(AI 또는 표준 미리보기)에
쓰는 입력값 정리 결과이기도 하다.
"""

import json
from pathlib import Path

TEMPLATES_PATH = Path(__file__).resolve().parent / "staff_templates.json"

_SENDER_INFO_KEYS = ("to", "cc", "from_org", "from_name")

# 확인된 신호로만 판단하는 중요 메일 키워드. 받는 사람 입력값에 아래
# 표현이 포함되면 "고객·거래처·임원 수신" 신호로 취급한다.
_VIP_KEYWORDS = ("고객", "거래처", "임원", "대표", "사장", "이사", "부장")

_deadline_field_ids = {"deadline"}
_request_content_field_ids = {"request_content", "request_detail"}


def load_templates():
    return json.loads(TEMPLATES_PATH.read_text(encoding="utf-8"))


def list_templates():
    return load_templates()


def get_template(template_id):
    for template in load_templates():
        if template["id"] == template_id:
            return template
    return None


def clean_values(template, values):
    """빈 값은 제거하고, 정의된 필드만 남긴다."""
    cleaned = {}
    for field in template["fields"]:
        fid = field["id"]
        raw = values.get(fid, "")
        val = raw.strip() if isinstance(raw, str) else raw
        if val:
            cleaned[fid] = val
    return cleaned


def missing_required(template, cleaned):
    missing = [f["label"] for f in template["fields"] if f.get("required") and not cleaned.get(f["id"])]
    at_least_one = template.get("at_least_one_of")
    if at_least_one and not any(cleaned.get(fid) for fid in at_least_one):
        labels = [f["label"] for f in template["fields"] if f["id"] in at_least_one]
        missing.append("다음 중 하나 이상 입력: " + ", ".join(labels))
    return missing


def detect_importance(template, cleaned):
    """확인된 신호(업무 유형, 기한 포함 여부, 요청 내용 존재, 수신자 키워드)만으로
    자동 중요도를 판단한다. 사실을 추론하지 않는다."""
    reasons = []
    template_id = template["id"]

    if template_id == "issue_report":
        reasons.append("이슈 보고 유형")
    if template_id == "schedule_change":
        reasons.append("일정 변경 유형")
    if any(cleaned.get(fid) for fid in _deadline_field_ids):
        reasons.append("기한 포함")
    if template_id == "request" or any(cleaned.get(fid) for fid in _request_content_field_ids):
        reasons.append("확인·지원 요청 포함")

    to_value = cleaned.get("to", "")
    if any(keyword in to_value for keyword in _VIP_KEYWORDS):
        reasons.append("고객·거래처·임원 수신")

    level = "중요" if reasons else "일반"
    return {"level": level, "reasons": reasons, "auto": True}


def build_instructions(template, cleaned):
    field_labels = {f["id"]: f["label"] for f in template["fields"]}
    lines = [template.get("description", ""), template.get("rules", ""), ""]
    lines.append("입력된 항목:")
    has_any = False
    for fid, val in cleaned.items():
        if fid in _SENDER_INFO_KEYS:
            continue
        has_any = True
        lines.append(f"- {field_labels.get(fid, fid)}: {val}")
    if not has_any:
        lines.append("(입력된 항목 없음)")
    return "\n".join(line for line in lines if line is not None)


def build_compose_request(template_id, values):
    template = get_template(template_id)
    if template is None:
        raise ValueError(f"알 수 없는 업무 유형입니다: {template_id}")

    cleaned = clean_values(template, values)
    missing = missing_required(template, cleaned)
    importance = detect_importance(template, cleaned)
    instructions = build_instructions(template, cleaned)

    return {
        "template_id": template_id,
        "template_label": template["label"],
        "fields": cleaned,
        "missing_required": missing,
        "importance": importance,
        "instructions": instructions,
    }

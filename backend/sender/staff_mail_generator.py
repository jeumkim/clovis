"""OpenAI 없이도 동작하는 표준 미리보기 생성기.

입력값에 없는 수치·날짜·원인·담당자·기한·사실은 만들어내지 않는다.
합계·차이·증감률 계산도 하지 않는다. 입력된 짧은 메모를 격식 있는
"~습니다." 문장으로 다듬는 최소한의 규칙만 적용한다.
"""

import re

_SENTENCE_ENDINGS = ("다", "요", "함", "임", "됨", "음")


def _has_batchim(word):
    if not word:
        return False
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        return (code - 0xAC00) % 28 != 0
    return False


def _i_ga(word):
    return "이" if _has_batchim(word) else "가"


def _eul_reul(word):
    return "을" if _has_batchim(word) else "를"


def _euro_ro(word):
    """으로/로 조사. 받침이 없거나 받침이 'ㄹ'이면 '로', 그 외에는 '으로'."""
    if not word:
        return "로"
    ch = word[-1]
    code = ord(ch)
    if 0xAC00 <= code <= 0xD7A3:
        jong = (code - 0xAC00) % 28
        if jong == 0 or jong == 8:
            return "로"
        return "으로"
    return "으로"


def _strip_trailing_dot(text):
    return text.rstrip(".!?").strip()


def _ensure_sentence(text):
    """짧은 메모를 의미를 바꾸지 않는 범위에서 완결된 문장으로 다듬는다."""
    text = text.strip()
    if not text:
        return ""
    if text[-1] in ".!?":
        return text
    if text.endswith(_SENTENCE_ENDINGS):
        return text + "."
    return text + "합니다."


def assemble_content(lines):
    """독립된 항목이 3개 이상이면 불릿, 아니면 이어지는 문장으로 정리한다."""
    sentences = [_ensure_sentence(line) for line in lines if line.strip()]
    sentences = [s for s in sentences if s]
    if not sentences:
        return ""
    if len(sentences) >= 3:
        return "\n".join(f"- {s}" for s in sentences)
    return " ".join(sentences)


def format_lines(lines, transform):
    """항목이 여러 개면 줄바꿈으로, 3개 이상이면 불릿으로 구분한다."""
    sentences = [transform(line.strip()) for line in lines if line.strip()]
    sentences = [s for s in sentences if s]
    if not sentences:
        return ""
    if len(sentences) == 1:
        return sentences[0]
    if len(sentences) >= 3:
        return "\n".join(f"- {s}" for s in sentences)
    return "\n".join(sentences)


REPLY_PURPOSE_INTRO = {
    "자동 구성": "",
    "수신 확인": "보내주신 메일 잘 확인하였습니다.",
    "요청 승인": "요청하신 사항에 대해 승인 안내드립니다.",
    "일정 안내": "문의주신 일정 관련하여 안내드립니다.",
    "자료 전달": "요청하신 자료를 아래와 같이 전달드립니다.",
    "추가 문의": "문의드릴 사항이 있어 회신드립니다.",
    "정중한 거절": "문의주신 사항에 대해 아래와 같이 회신드립니다.",
}

_SUBJECT_LINE_RE = re.compile(r"^(제목|subject)\s*[:：]\s*(.+)$", re.IGNORECASE)


def extract_original_subject(received_mail):
    for line in received_mail.splitlines():
        m = _SUBJECT_LINE_RE.match(line.strip())
        if m:
            return m.group(2).strip()
    return None


def build_reply_subject(received_mail):
    original = extract_original_subject(received_mail or "")
    if original:
        return f"Re: {original}"
    return "회신 안내"


def generate_reply(cleaned):
    received_mail = cleaned.get("received_mail", "")
    confirmed_content = cleaned.get("confirmed_content", "")
    purpose = cleaned.get("reply_purpose", "자동 구성")

    subject = build_reply_subject(received_mail)
    intro = REPLY_PURPOSE_INTRO.get(purpose, "")
    content = assemble_content(confirmed_content.splitlines())

    core_parts = [p for p in (intro, content) if p]
    core_text = "\n\n".join(core_parts)
    return subject, core_text


def generate_report(cleaned):
    completed = cleaned.get("completed_tasks", "")
    in_progress = cleaned.get("in_progress_tasks", "")
    planned = cleaned.get("planned_tasks", "")
    request_content = cleaned.get("request_content", "")

    parts = []
    if completed:
        parts.append(format_lines(completed.splitlines(), lambda l: f"{_strip_trailing_dot(l)} 업무를 완료했습니다."))
    if in_progress:
        parts.append(format_lines(in_progress.splitlines(), lambda l: f"{_strip_trailing_dot(l)} 업무를 진행하고 있습니다."))
    if planned:
        parts.append(format_lines(planned.splitlines(), lambda l: f"{_strip_trailing_dot(l)} 업무를 진행할 예정입니다."))
    if request_content:
        parts.append(
            format_lines(
                request_content.splitlines(),
                lambda l: f"{_strip_trailing_dot(l)}{_eul_reul(_strip_trailing_dot(l))} 부탁드립니다.",
            )
        )

    core_text = "\n\n".join(p for p in parts if p)
    subject = "[업무보고] 업무 진행 사항 안내"
    return subject, core_text


def generate_request(cleaned):
    subject_target = cleaned.get("request_subject", "")
    reason = cleaned.get("request_reason", "")
    detail = cleaned.get("request_detail", "")
    deadline = cleaned.get("deadline", "")

    intro = f"{subject_target} 관련하여 협조를 요청드립니다." if subject_target else ""
    reason_sentence = _ensure_sentence(reason) if reason else ""
    detail_sentence = _ensure_sentence(detail) if detail else ""
    body_middle = " ".join(p for p in (reason_sentence, detail_sentence) if p)
    deadline_sentence = f"{deadline}까지 회신 부탁드립니다." if deadline else ""

    core_text = "\n\n".join(p for p in (intro, body_middle, deadline_sentence) if p)
    subject = f"[협조 요청] {subject_target}" if subject_target else "[협조 요청]"
    return subject, core_text


def generate_schedule_change(cleaned):
    subject_target = cleaned.get("schedule_subject", "")
    old = cleaned.get("old_schedule", "")
    new = cleaned.get("new_schedule", "")
    reason = cleaned.get("reason", "")
    confirm = cleaned.get("confirm_request", "")

    if reason:
        main = (
            f"{reason}{_euro_ro(reason)} 인해 {subject_target}{_i_ga(subject_target)} "
            f"{old}에서 {new}{_euro_ro(new)} 변경되어 안내드립니다."
        )
    else:
        main = f"{subject_target}{_i_ga(subject_target)} {old}에서 {new}{_euro_ro(new)} 변경되어 안내드립니다."

    parts = [main]
    if confirm:
        confirm_clean = _strip_trailing_dot(confirm)
        parts.append(f"{confirm_clean}{_eul_reul(confirm_clean)} 부탁드립니다.")

    core_text = "\n\n".join(parts)
    subject = f"[일정 변경] {subject_target} 안내" if subject_target else "[일정 변경] 안내"
    return subject, core_text


def generate_meeting_summary(cleaned):
    topic = cleaned.get("meeting_topic", "")
    date = cleaned.get("meeting_date", "")
    decisions = cleaned.get("decisions", "")
    action_items = cleaned.get("action_items", "")

    if topic and date:
        intro = f"{date}에 진행된 {topic} 회의 결과를 공유드립니다."
    elif topic:
        intro = f"{topic} 회의 결과를 공유드립니다."
    else:
        intro = "회의 결과를 공유드립니다."

    decisions_block = format_lines(decisions.splitlines(), _ensure_sentence) if decisions else ""
    action_block = (
        format_lines(
            action_items.splitlines(),
            lambda l: f"{_strip_trailing_dot(l)}{_eul_reul(_strip_trailing_dot(l))} 부탁드립니다.",
        )
        if action_items
        else ""
    )

    core_text = "\n\n".join(p for p in (intro, decisions_block, action_block) if p)
    subject = f"[회의 결과] {topic}" if topic else "[회의 결과]"
    return subject, core_text


def generate_material_request(cleaned):
    name = cleaned.get("material_name", "")
    purpose = cleaned.get("purpose", "")
    deadline = cleaned.get("deadline", "")
    method = cleaned.get("submit_method", "")

    intro = f"{name} 제출을 요청드립니다." if name else "자료 제출을 요청드립니다."
    purpose_sentence = ""
    if purpose:
        purpose_clean = _strip_trailing_dot(purpose)
        purpose_sentence = f"{purpose_clean}{_eul_reul(purpose_clean)} 위해 필요합니다."
    deadline_sentence = f"{deadline}까지 제출 부탁드립니다." if deadline else ""
    method_sentence = f"제출 방법은 {method}입니다." if method else ""

    core_text = "\n\n".join(p for p in (intro, purpose_sentence, deadline_sentence, method_sentence) if p)
    subject = f"[자료 제출 요청] {name}" if name else "[자료 제출 요청]"
    return subject, core_text


def generate_issue_report(cleaned):
    title = cleaned.get("issue_title", "")
    detail = cleaned.get("issue_detail", "")
    impact = cleaned.get("impact", "")
    action = cleaned.get("action_taken", "")

    intro = f"{title} 관련 이슈를 보고드립니다." if title else "이슈를 보고드립니다."
    detail_sentence = _ensure_sentence(detail) if detail else ""
    impact_sentence = ""
    if impact:
        impact_clean = _strip_trailing_dot(impact)
        impact_sentence = f"이번 이슈로 {impact_clean}{_eul_reul(impact_clean)} 미치고 있습니다."
    action_sentence = ""
    if action:
        action_clean = _strip_trailing_dot(action)
        action_sentence = f"현재 {action_clean}{_eul_reul(action_clean)} 진행하고 있습니다."

    core_text = "\n\n".join(p for p in (intro, detail_sentence, impact_sentence, action_sentence) if p)
    subject = f"[이슈 보고] {title}" if title else "[이슈 보고]"
    return subject, core_text


_GENERATORS = {
    "reply": generate_reply,
    "report": generate_report,
    "request": generate_request,
    "schedule_change": generate_schedule_change,
    "meeting_summary": generate_meeting_summary,
    "material_request": generate_material_request,
    "issue_report": generate_issue_report,
}


def wrap_body(core_text, from_org, from_name):
    lines = ["안녕하세요."]
    if from_org:
        lines.append(f"{from_org}입니다.")
    if core_text:
        lines.append(core_text)
    lines.append("확인 부탁드립니다.")
    lines.append("감사합니다.")
    lines.append(f"{from_name} 드림" if from_name else "드림")
    return "\n\n".join(lines)


def generate(template_id, cleaned):
    fn = _GENERATORS.get(template_id)
    if fn is None:
        raise ValueError(f"지원하지 않는 업무 유형입니다: {template_id}")
    subject, core_text = fn(cleaned)
    body = wrap_body(core_text, cleaned.get("from_org", ""), cleaned.get("from_name", ""))
    return subject, body

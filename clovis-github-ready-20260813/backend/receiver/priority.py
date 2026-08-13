"""우선순위 대시보드 점수 계산.

변경폭(일정 변경 일수, 화물량 변경률)과 긴급도(입항 임박 여부)를 조합해
점수를 매긴다. DB 미등록/이상값 경고가 있으면 사람이 먼저 봐야 하므로
가산점을 준다. 가중치는 이 파일에서만 조정하면 된다.
"""

URGENCY_WINDOW_DAYS = 5
URGENCY_WEIGHT_PER_DAY = 10
SCHEDULE_WEIGHT_PER_DAY = 5
CARGO_WEIGHT_PER_PERCENT = 1
DB_MISSING_BONUS = 50
WARNING_BONUS = 30


def compute_priority(summary):
    """summary: {schedule_change_days, cargo_change_percent, days_until_arrival,
    db_missing, warning_count} (수치 필드는 None 가능)"""
    breakdown = {}

    days_until = summary.get("days_until_arrival")
    if days_until is None:
        urgency = 0.0
    else:
        urgency = max(0.0, URGENCY_WINDOW_DAYS - days_until) * URGENCY_WEIGHT_PER_DAY
    if urgency:
        breakdown["긴급도(입항 임박)"] = round(urgency, 1)

    schedule_days = summary.get("schedule_change_days") or 0
    schedule_score = schedule_days * SCHEDULE_WEIGHT_PER_DAY
    if schedule_score:
        breakdown["일정 변경폭"] = round(schedule_score, 1)

    cargo_pct = summary.get("cargo_change_percent") or 0
    cargo_score = cargo_pct * CARGO_WEIGHT_PER_PERCENT
    if cargo_score:
        breakdown["화물량 변경폭"] = round(cargo_score, 1)

    exception_score = 0.0
    if summary.get("db_missing"):
        exception_score += DB_MISSING_BONUS
        breakdown["DB 미등록"] = DB_MISSING_BONUS

    warning_count = summary.get("warning_count", 0) or 0
    if warning_count:
        bonus = WARNING_BONUS * warning_count
        exception_score += bonus
        breakdown[f"이상값 경고 {warning_count}건"] = bonus

    total = urgency + schedule_score + cargo_score + exception_score
    return {"total": round(total, 1), "breakdown": breakdown}


_SORT_KEYS = {
    "priority": lambda c: -c["priority"]["total"],
    "schedule_days": lambda c: -(c["summary"].get("schedule_change_days") or 0),
    "cargo_percent": lambda c: -(c["summary"].get("cargo_change_percent") or 0),
    "urgency": lambda c: (
        c["summary"]["days_until_arrival"]
        if c["summary"].get("days_until_arrival") is not None
        else float("inf")
    ),
}


def sort_cases(cases, sort_key="priority"):
    keyfn = _SORT_KEYS.get(sort_key, _SORT_KEYS["priority"])
    return sorted(cases, key=keyfn)

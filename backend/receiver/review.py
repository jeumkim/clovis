"""메일에서 추출한 한 건(case)을 검토 화면에 필요한 형태로 조립한다.

DB 조회 -> 필드별 대조/하이라이트 -> 이상값 경고 -> 캘린더 비교 ->
우선순위 점수까지 한 건 단위로 묶어서 반환한다. 프론트엔드는 이 결과를
그대로 카드 하나로 렌더링하면 된다.
"""

from datetime import datetime

import calendar_view
import db
import highlight
import priority
import validation


def build_review_card(case, today=None):
    today = today or datetime.now()
    fields = case["fields"]

    lookup_seed = {key: info.get("value") for key, info in fields.items()}
    existing = db.find_ship_record(lookup_seed)
    db_missing = existing is None

    field_rows = highlight.build_field_diff(fields, existing)
    field_by_key = {row["key"]: row for row in field_rows}

    arrival_row = field_by_key.get("arrival_datetime", {})
    old_arrival_dt = validation.normalize_datetime(arrival_row.get("old_value"))
    new_arrival_dt = validation.normalize_datetime(arrival_row.get("new_value"))

    warnings = []
    if new_arrival_dt is not None and validation.check_past_datetime(arrival_row.get("new_value"), now=today):
        warnings.append(
            {
                "type": "past_arrival",
                "message": f"입항일({arrival_row.get('new_value')})이 이미 지난 날짜입니다.",
            }
        )

    cargo_row = field_by_key.get("cargo_volume", {})
    max_capacity = (existing or {}).get("max_cargo_capacity")
    if cargo_row.get("new_value") and max_capacity and validation.check_over_capacity(
        cargo_row["new_value"], max_capacity
    ):
        warnings.append(
            {
                "type": "over_capacity",
                "message": f"화물량({cargo_row['new_value']})이 최대 적재량({max_capacity})을 초과했습니다.",
            }
        )

    calendar_marks = None
    if arrival_row.get("status") in ("changed", "no_baseline") and new_arrival_dt is not None:
        calendar_marks = calendar_view.build_calendar_marks(today, old_arrival_dt, new_arrival_dt)

    schedule_change_days = None
    if arrival_row.get("status") == "changed" and old_arrival_dt is not None and new_arrival_dt is not None:
        schedule_change_days = abs((new_arrival_dt - old_arrival_dt).total_seconds()) / 86400

    cargo_change_percent = None
    if cargo_row.get("status") == "changed":
        old_n = validation.normalize_number(cargo_row.get("old_value"))
        new_n = validation.normalize_number(cargo_row.get("new_value"))
        if old_n and new_n:
            cargo_change_percent = abs(new_n - old_n) / old_n * 100

    days_until_arrival = None
    reference_dt = new_arrival_dt or old_arrival_dt
    if reference_dt is not None:
        days_until_arrival = (reference_dt - today).total_seconds() / 86400

    summary = {
        "schedule_change_days": schedule_change_days,
        "cargo_change_percent": cargo_change_percent,
        "days_until_arrival": days_until_arrival,
        "db_missing": db_missing,
        "warning_count": len(warnings),
    }
    priority_result = priority.compute_priority(summary)

    ship_identity = {
        "ship_id": (existing or {}).get("ship_id") or fields.get("ship_id", {}).get("value"),
        "ship_name": (existing or {}).get("ship_name") or fields.get("ship_name", {}).get("value"),
        "call_sign": (existing or {}).get("call_sign") or fields.get("call_sign", {}).get("value"),
    }

    return {
        "case_id": case["case_id"],
        "ship": ship_identity,
        "db_missing": db_missing,
        "fields": field_rows,
        "warnings": warnings,
        "calendar": calendar_marks,
        "summary": summary,
        "priority": priority_result,
        "update_enabled": not db_missing,
    }

"""일정 변경 3-way 비교(오늘 / 기존 / 변경)를 위한 달력 격자 데이터를 만든다.

프론트엔드는 이 구조를 그대로 요일별 격자로 그리기만 하면 되므로, 날짜
계산(월 경계, 요일 정렬 등)은 여기서 모두 끝낸다.
"""

import calendar as _calendar
from datetime import date, datetime


def _to_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def build_calendar_marks(today, old_dt=None, new_dt=None):
    """today/old_dt/new_dt: datetime|date|None.

    반환: [{"year": int, "month": int, "weeks": [[cell|None, ...], ...]}]
    cell = {"day": int, "is_today": bool, "is_old": bool, "is_new": bool}
    old_dt/new_dt가 서로 다른 달이면 두 달치 격자를 모두 반환한다.
    """
    today_d = _to_date(today)
    old_d = _to_date(old_dt)
    new_d = _to_date(new_dt)

    months = sorted({(d.year, d.month) for d in (today_d, old_d, new_d) if d is not None})
    cal = _calendar.Calendar(firstweekday=6)  # 일요일 시작

    result = []
    for year, month in months:
        weeks = []
        for week in cal.monthdayscalendar(year, month):
            week_cells = []
            for day in week:
                if day == 0:
                    week_cells.append(None)
                    continue
                d = date(year, month, day)
                week_cells.append(
                    {
                        "day": day,
                        "is_today": today_d is not None and d == today_d,
                        "is_old": old_d is not None and d == old_d,
                        "is_new": new_d is not None and d == new_d,
                    }
                )
            weeks.append(week_cells)
        result.append({"year": year, "month": month, "weeks": weeks})
    return result

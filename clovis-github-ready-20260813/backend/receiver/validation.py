"""표기 정규화 및 이상값 검증.

"1300"과 "1,300톤"처럼 표기가 제각각인 값을 비교 전에 일관된 포맷(숫자만
추출, 날짜는 datetime)으로 정규화한 뒤 대조한다. 화물량 초과, 과거
입항일처럼 명백히 이상한 값은 여기서 판별해 review.py가 경고로 표시한다.
"""

import re
from datetime import datetime

_NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
_DATETIME_RE = re.compile(
    r"(\d{4})[-.년]\s*(\d{1,2})[-.월]\s*(\d{1,2})일?(?:\s+(\d{1,2}):(\d{2}))?"
)

# 날짜/숫자 비교가 필요한 필드. columns.py의 key와 맞춘다.
DATE_FIELD_KEYS = {"arrival_datetime", "departure_datetime", "ciq_date", "repair_datetime"}
NUMBER_FIELD_KEYS = {"cargo_volume", "gross_tonnage"}


def normalize_number(text):
    """"1,300 TEU" / "1300톤" 같은 표기에서 숫자만 뽑아낸다."""
    if not text:
        return None
    m = _NUMBER_RE.search(str(text))
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def normalize_datetime(text):
    """"2026-08-14 09:00" / "2026년 8월 14일" 등을 datetime으로 정규화한다."""
    if not text:
        return None
    m = _DATETIME_RE.search(str(text))
    if not m:
        return None
    year, month, day, hour, minute = m.groups()
    try:
        return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))
    except ValueError:
        return None


def field_kind(field_key):
    if field_key in DATE_FIELD_KEYS:
        return "date"
    if field_key in NUMBER_FIELD_KEYS:
        return "number"
    return "text"


def values_equal(field_key, old_text, new_text):
    """정규화한 뒤 같은 값인지 비교한다. 정규화에 실패하면 문자열 비교로 대체한다."""
    if old_text is None or new_text is None:
        return False

    kind = field_kind(field_key)
    if kind == "date":
        old_dt, new_dt = normalize_datetime(old_text), normalize_datetime(new_text)
        if old_dt is not None and new_dt is not None:
            return old_dt == new_dt
    elif kind == "number":
        old_n, new_n = normalize_number(old_text), normalize_number(new_text)
        if old_n is not None and new_n is not None:
            return old_n == new_n

    return str(old_text).strip() == str(new_text).strip()


def check_past_datetime(text, now=None):
    """입항일이 이미 지난 날짜인지 확인한다."""
    dt = normalize_datetime(text)
    if dt is None:
        return False
    now = now or datetime.now()
    return dt < now


def check_over_capacity(cargo_text, max_capacity_text):
    """화물량이 선박 최대 적재량을 초과하는지 확인한다."""
    cargo_n = normalize_number(cargo_text)
    max_n = normalize_number(max_capacity_text)
    if cargo_n is None or max_n is None:
        return False
    return cargo_n > max_n

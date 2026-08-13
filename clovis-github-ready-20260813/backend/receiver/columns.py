# PORT-MIS_HPNT_raw.xlsx 포맷 기준 목표 컬럼 정의.
#
# `extracted=True`인 컬럼만 이번 단계(mock/실제 AI 추출)에서 실제로 값을
# 채운다. 나머지는 향후 단계를 위한 컬럼 정의만 남겨둔 것이며 현재는
# DB 대조 대상에서 제외된다.

PORT_MIS_COLUMNS = [
    {"key": "port_name", "label": "항명", "extracted": True},
    {"key": "call_sign", "label": "호출부호", "extracted": True},
    {"key": "ship_name", "label": "선명", "extracted": True},
    {"key": "arrival_count", "label": "입항횟수", "extracted": False},
    {"key": "arrival_count_type", "label": "입항횟수구분", "extracted": False},
    {"key": "in_out_flag", "label": "외내", "extracted": False},
    {"key": "entry_exit_flag", "label": "입출", "extracted": False},
    {"key": "gross_tonnage", "label": "총톤수", "extracted": False},
    {"key": "arrival_datetime", "label": "입항일시", "extracted": True},
    {"key": "departure_datetime", "label": "출항일시", "extracted": False},
    {"key": "ciq_date", "label": "CIQ수속일자", "extracted": False},
    {"key": "repair_datetime", "label": "수리일시", "extracted": False},
    {"key": "voyage_type", "label": "항해구분", "extracted": False},
    {"key": "mrn_number", "label": "MRN번호", "extracted": False},
    {"key": "berth_location", "label": "계선장소", "extracted": False},
    {"key": "next_port", "label": "차항지", "extracted": True},
    # 메일에서 말하는 "출항지"는 이 배에 대한 PORT-MIS 기준 "전출항지"(이전
    # 출발지)에 대응한다.
    {"key": "previous_port", "label": "전출항지", "extracted": True},
    {"key": "ship_purpose", "label": "선박용도", "extracted": False},
    {"key": "crew_foreign", "label": "선원수(외항)", "extracted": False},
    {"key": "crew_domestic", "label": "선원수(내항)", "extracted": False},
    {"key": "passengers", "label": "승객", "extracted": False},
    {"key": "tugboat", "label": "예선", "extracted": False},
    {"key": "pilotage", "label": "도선", "extracted": False},
    {"key": "barge_call_sign_1", "label": "부선호출부호1", "extracted": False},
    {"key": "barge_call_sign_2", "label": "부선호출부호2", "extracted": False},
]

# PORT-MIS 원본 컬럼은 아니지만, 이번 서비스(수신 메일 대조)를 위해 함께
# 추적하는 보조 항목.
SUPPLEMENTARY_COLUMNS = [
    {"key": "ship_id", "label": "선박ID", "extracted": True},
    {"key": "cargo_volume", "label": "화물량", "extracted": True},
]

ALL_COLUMNS = PORT_MIS_COLUMNS + SUPPLEMENTARY_COLUMNS

COLUMN_LABELS = {c["key"]: c["label"] for c in ALL_COLUMNS}

# 이번 단계에서 메일 본문으로부터 실제로 추출/대조하는 핵심 필드.
CORE_EXTRACT_KEYS = [c["key"] for c in ALL_COLUMNS if c["extracted"]]

"""추출된 값과 기존 DB 값을 필드별로 비교해 변경 여부를 판정한다.

각 필드는 다음 네 가지 상태 중 하나를 가진다.
- "changed": DB 값과 다르다 (프론트에서 노란 배경 + 볼드로 강조)
- "unchanged": DB 값과 같다 (강조하지 않음)
- "missing": extraction_failed=True (메일에서 이 필드를 추출하지 못했다.
  "추출 실패"로 표시하며, 임의 값을 채우지 않는다)
- "no_baseline": 선박 자체가 DB에 없어 비교 대상이 없다 (DB 미등록
  카드 전체에 적용되지만, 값 자체는 추출됐을 수 있다)
"""

from columns import COLUMN_LABELS, CORE_EXTRACT_KEYS
import validation


def build_field_diff(extracted_fields, existing_record):
    """extracted_fields: {key: {"value", "evidence", "confidence", "extraction_failed"}}
    existing_record: DB 레코드 dict, 없으면 None (DB 미등록)
    """
    rows = []
    for key in CORE_EXTRACT_KEYS:
        extracted = extracted_fields.get(key) or {}
        new_value = extracted.get("value")
        evidence = extracted.get("evidence")
        confidence = extracted.get("confidence")
        extraction_failed = extracted.get("extraction_failed", new_value is None)
        old_value = (existing_record or {}).get(key)

        if existing_record is None:
            status = "missing" if extraction_failed else "no_baseline"
        elif extraction_failed:
            status = "missing"
        elif old_value is None:
            status = "changed"
        elif validation.values_equal(key, old_value, new_value):
            status = "unchanged"
        else:
            status = "changed"

        rows.append(
            {
                "key": key,
                "label": COLUMN_LABELS.get(key, key),
                "old_value": old_value,
                "new_value": new_value,
                "evidence": evidence,
                "confidence": confidence,
                "extraction_failed": extraction_failed,
                "status": status,
            }
        )
    return rows

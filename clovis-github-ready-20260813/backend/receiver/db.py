"""SQLite 기반 선박 DB + 변경 이력(감사 추적).

- ships 테이블: 선박 마스터 데이터. apply_approved_changes()만 이 표를
  UPDATE한다(승인된 필드만).
- change_history 테이블: append-only. 이 파일의 그 어떤 함수도 이
  테이블에 UPDATE/DELETE를 실행하지 않는다 — record_history()가 매번
  새 행을 INSERT할 뿐이다.

DB 파일 경로는 secret_manager.get_db_path_override()(.env의
RECEIVER_DB_PATH)로 바꿀 수 있다(테스트 격리용). 최초 기동 시
ships 테이블이 비어 있으면 data/ships_seed.json으로 시드한다.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from columns import ALL_COLUMNS
import secret_manager

_BASE_DIR = Path(__file__).resolve().parent
_DEFAULT_DB_PATH = _BASE_DIR / "data" / "receiver.db"
SEED_JSON_PATH = _BASE_DIR / "data" / "ships_seed.json"

# ships 테이블 컬럼 = PORT-MIS 목표 컬럼 전체 + 화물량 관련 보조 컬럼.
SHIP_COLUMNS = [c["key"] for c in ALL_COLUMNS] + ["max_cargo_capacity"]


def _db_path() -> Path:
    override = secret_manager.get_db_path_override()
    return Path(override) if override else _DEFAULT_DB_PATH


def get_connection() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """앱 시작 시 1회 호출. 테이블이 없으면 만들고, ships가 비어 있으면
    시드 데이터를 채운다. 여러 번 호출해도 안전하다(idempotent)."""
    conn = get_connection()
    try:
        other_cols_sql = ", ".join(f'"{c}" TEXT' for c in SHIP_COLUMNS if c not in ("ship_id", "call_sign"))
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS ships (
                ship_id TEXT PRIMARY KEY,
                call_sign TEXT UNIQUE,
                {other_cols_sql}
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS change_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                ship_call_sign TEXT,
                action TEXT NOT NULL CHECK(action IN ('approved', 'rejected')),
                changed_at TEXT NOT NULL,
                changed_by TEXT NOT NULL,
                mail_reference TEXT,
                changes_json TEXT NOT NULL
            )
            """
        )
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM ships").fetchone()[0]
        if count == 0 and SEED_JSON_PATH.exists():
            seed_ships = json.loads(SEED_JSON_PATH.read_text(encoding="utf-8"))
            cols_sql = ", ".join(f'"{c}"' for c in SHIP_COLUMNS)
            placeholders_sql = ", ".join(f":{c}" for c in SHIP_COLUMNS)
            for ship in seed_ships:
                row = {c: ship.get(c) for c in SHIP_COLUMNS}
                conn.execute(f"INSERT INTO ships ({cols_sql}) VALUES ({placeholders_sql})", row)
            conn.commit()
    finally:
        conn.close()


def find_ship_record(lookup: dict) -> dict | None:
    """추출된 필드의 선박ID 또는 호출부호를 키로 DB에서 동일 선박 레코드를 찾는다."""
    ship_id = lookup.get("ship_id")
    call_sign = lookup.get("call_sign")
    conn = get_connection()
    try:
        row = None
        if ship_id:
            row = conn.execute("SELECT * FROM ships WHERE ship_id = ?", (ship_id,)).fetchone()
        if row is None and call_sign:
            row = conn.execute("SELECT * FROM ships WHERE call_sign = ?", (call_sign,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def apply_approved_changes(call_sign: str, changes: dict) -> dict | None:
    """승인된 필드만 갱신한다. ships 테이블에 UPDATE를 실행하는 유일한 함수."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT * FROM ships WHERE call_sign = ?", (call_sign,)).fetchone()
        if existing is None:
            return None
        if changes:
            set_clause = ", ".join(f'"{k}" = :{k}' for k in changes)
            params = dict(changes)
            params["call_sign"] = call_sign
            conn.execute(f"UPDATE ships SET {set_clause} WHERE call_sign = :call_sign", params)
            conn.commit()
        row = conn.execute("SELECT * FROM ships WHERE call_sign = ?", (call_sign,)).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def record_history(case_id: str, ship_call_sign, action: str, changed_by: str, mail_reference, changes: dict) -> dict:
    """change_history에 새 행을 추가한다(append-only). UPDATE/DELETE는 절대 쓰지 않는다."""
    conn = get_connection()
    try:
        changed_at = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO change_history "
            "(case_id, ship_call_sign, action, changed_at, changed_by, mail_reference, changes_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                case_id,
                ship_call_sign,
                action,
                changed_at,
                changed_by,
                mail_reference,
                json.dumps(changes, ensure_ascii=False),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM change_history WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(row)
    finally:
        conn.close()


def get_latest_decision(case_id: str) -> dict | None:
    """이 case_id가 이미 승인/반려되었는지 확인한다(가장 최근 이력 1건)."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM change_history WHERE case_id = ? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def list_history(limit: int = 50) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM change_history ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

"""Audit log for human overrides to AI-suggested scores and weights.

Every change a human makes to a criterion score or criterion weight is recorded
here so that every final score in the system is traceable to either an AI
extraction (provenance in extraction.py) or a logged human override (here).

Database: SQLite, path from env var AUDIT_DB_PATH (default: data/audit.db).
Each public function opens its own connection — there is no module-level
persistent connection, so re-opening after a process restart is transparent.
"""

import os
import sqlite3
from datetime import datetime, timezone
from typing import Literal

_DEFAULT_DB_PATH = os.path.join("data", "audit.db")

FieldType = Literal["score", "weight"]

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS overrides (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id   TEXT    NOT NULL,
    criterion_key TEXT    NOT NULL,
    old_value     REAL    NOT NULL,
    new_value     REAL    NOT NULL,
    changed_at    TEXT    NOT NULL,
    field         TEXT    NOT NULL CHECK (field IN ('score', 'weight'))
);
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_overrides_analysis
ON overrides (analysis_id, changed_at);
"""


def _db_path(override: str | None = None) -> str:
    return override or os.environ.get("AUDIT_DB_PATH", _DEFAULT_DB_PATH)


def _connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create the overrides table and index if they don't already exist."""
    path = _db_path(db_path)
    with _connect(path) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_SQL)


def log_override(
    analysis_id: str,
    criterion_key: str,
    old_value: float,
    new_value: float,
    field: FieldType,
    db_path: str | None = None,
) -> int:
    """Insert one override record and return its new row id.

    Args:
        analysis_id:   Stable identifier for this review session (e.g. a UUID
                       or filename-derived slug).
        criterion_key: One of the 6 CRITERIA keys.
        old_value:     The value being replaced (AI-suggested or prior human value).
        new_value:     The value the human entered.
        field:         "score" (1–9) or "weight" (any positive float).
        db_path:       Optional path override; defaults to AUDIT_DB_PATH env var.

    Returns:
        The inserted row's id.
    """
    path = _db_path(db_path)
    init_db(path)
    changed_at = datetime.now(timezone.utc).isoformat()
    with _connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO overrides (analysis_id, criterion_key, old_value, new_value,
                                   changed_at, field)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (analysis_id, criterion_key, old_value, new_value, changed_at, field),
        )
        return cur.lastrowid


def get_audit_trail(
    analysis_id: str,
    db_path: str | None = None,
) -> list[dict]:
    """Return all overrides for analysis_id ordered by changed_at ascending.

    Args:
        analysis_id: The review session identifier to query.
        db_path:     Optional path override.

    Returns:
        List of dicts with keys: id, analysis_id, criterion_key, old_value,
        new_value, changed_at, field.  Empty list if none found.
    """
    path = _db_path(db_path)
    init_db(path)
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT id, analysis_id, criterion_key, old_value, new_value,
                   changed_at, field
            FROM overrides
            WHERE analysis_id = ?
            ORDER BY changed_at ASC
            """,
            (analysis_id,),
        ).fetchall()
    return [dict(row) for row in rows]

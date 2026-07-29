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

# ---------------------------------------------------------------------------
# analyze_requests — one row per completed /analyze call, used for the demo's
# per-IP / global daily rate limiting and for cost tracking (see app/security.py).
# ---------------------------------------------------------------------------

_CREATE_ANALYZE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS analyze_requests (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ip               TEXT    NOT NULL,
    requested_at     TEXT    NOT NULL,
    approx_cost_usd  REAL    NOT NULL
);
"""

_CREATE_ANALYZE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_analyze_requests_time
ON analyze_requests (requested_at, ip);
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
    """Create the overrides/analyze_requests tables and indexes if they don't already exist."""
    path = _db_path(db_path)
    with _connect(path) as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute(_CREATE_INDEX_SQL)
        conn.execute(_CREATE_ANALYZE_TABLE_SQL)
        conn.execute(_CREATE_ANALYZE_INDEX_SQL)


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


def log_analyze_request(
    ip: str,
    approx_cost_usd: float,
    db_path: str | None = None,
) -> int:
    """Record one completed /analyze call for rate limiting and cost tracking.

    Args:
        ip:              Client IP the request came from (see app/security.py).
        approx_cost_usd: Cost of the Claude calls this analysis made.
        db_path:         Optional path override; defaults to AUDIT_DB_PATH env var.

    Returns:
        The inserted row's id.
    """
    path = _db_path(db_path)
    init_db(path)
    requested_at = datetime.now(timezone.utc).isoformat()
    with _connect(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO analyze_requests (ip, requested_at, approx_cost_usd)
            VALUES (?, ?, ?)
            """,
            (ip, requested_at, approx_cost_usd),
        )
        return cur.lastrowid


def count_analyze_requests(
    since: datetime,
    ip: str | None = None,
    db_path: str | None = None,
) -> int:
    """Count /analyze calls logged at or after `since`, optionally scoped to one IP.

    Args:
        since:   Only count rows with requested_at >= this timestamp.
        ip:      If given, count only requests from this IP. Otherwise count all.
        db_path: Optional path override.

    Returns:
        Matching row count.
    """
    path = _db_path(db_path)
    init_db(path)
    since_iso = since.isoformat()
    with _connect(path) as conn:
        if ip is not None:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM analyze_requests WHERE requested_at >= ? AND ip = ?",
                (since_iso, ip),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM analyze_requests WHERE requested_at >= ?",
                (since_iso,),
            ).fetchone()
    return row["n"]

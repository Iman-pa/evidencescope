"""Tests for app/audit.py.

Key test: after writing two overrides and fully closing the DB connection,
open a brand-new connection (simulating an app restart) and confirm both
records are present in insertion order.
"""

import os
import tempfile
import time

import pytest

from app.audit import get_audit_trail, init_db, log_override


@pytest.fixture()
def tmp_db(tmp_path):
    """Yield a path to a fresh temp DB file; deleted after each test."""
    return str(tmp_path / "test_audit.db")


# ---------------------------------------------------------------------------
# Core persistence test — survives connection close/reopen
# ---------------------------------------------------------------------------

def test_overrides_persist_across_reconnection(tmp_db):
    """Write two overrides, close all connections, reopen, confirm both exist."""
    analysis_id = "kerendia-2026-test"

    # --- First "session": log two overrides and close ---------------------
    row1 = log_override(
        analysis_id=analysis_id,
        criterion_key="clinical_benefit",
        old_value=6.0,
        new_value=7.0,
        field="score",
        db_path=tmp_db,
    )
    # Small sleep ensures changed_at timestamps are distinct (ISO 8601 microseconds)
    time.sleep(0.01)
    row2 = log_override(
        analysis_id=analysis_id,
        criterion_key="budget_impact",
        old_value=3.0,
        new_value=2.0,
        field="score",
        db_path=tmp_db,
    )

    # Both inserts returned valid row ids
    assert isinstance(row1, int) and row1 > 0
    assert isinstance(row2, int) and row2 > row1

    # --- Simulate app restart: do NOT reuse any prior connection ----------
    # get_audit_trail opens a completely new sqlite3.connect() call.
    trail = get_audit_trail(analysis_id, db_path=tmp_db)

    assert len(trail) == 2, f"Expected 2 overrides, got {len(trail)}"

    # Order: oldest first (ORDER BY changed_at ASC)
    first, second = trail

    assert first["criterion_key"] == "clinical_benefit"
    assert first["old_value"] == 6.0
    assert first["new_value"] == 7.0
    assert first["field"] == "score"

    assert second["criterion_key"] == "budget_impact"
    assert second["old_value"] == 3.0
    assert second["new_value"] == 2.0
    assert second["field"] == "score"

    # Timestamps are in ascending order
    assert first["changed_at"] < second["changed_at"]


# ---------------------------------------------------------------------------
# Isolation: different analysis_ids don't bleed into each other
# ---------------------------------------------------------------------------

def test_audit_trail_isolation(tmp_db):
    """Overrides for analysis A must not appear in analysis B's trail."""
    log_override("analysis-A", "safety", 5.0, 4.0, "score", db_path=tmp_db)
    log_override("analysis-B", "feasibility", 6.0, 8.0, "score", db_path=tmp_db)

    trail_a = get_audit_trail("analysis-A", db_path=tmp_db)
    trail_b = get_audit_trail("analysis-B", db_path=tmp_db)

    assert len(trail_a) == 1
    assert trail_a[0]["criterion_key"] == "safety"

    assert len(trail_b) == 1
    assert trail_b[0]["criterion_key"] == "feasibility"


# ---------------------------------------------------------------------------
# Weight overrides are stored correctly
# ---------------------------------------------------------------------------

def test_weight_override_stored(tmp_db):
    """field='weight' round-trips correctly."""
    log_override("w-test", "cost_effectiveness", 0.20, 0.30, "weight", db_path=tmp_db)
    trail = get_audit_trail("w-test", db_path=tmp_db)

    assert len(trail) == 1
    row = trail[0]
    assert row["field"] == "weight"
    assert abs(row["old_value"] - 0.20) < 1e-9
    assert abs(row["new_value"] - 0.30) < 1e-9


# ---------------------------------------------------------------------------
# Empty trail for unknown analysis_id
# ---------------------------------------------------------------------------

def test_empty_trail_for_unknown_analysis(tmp_db):
    init_db(tmp_db)
    trail = get_audit_trail("does-not-exist", db_path=tmp_db)
    assert trail == []


# ---------------------------------------------------------------------------
# Multiple overrides on same criterion — all recorded, all ordered
# ---------------------------------------------------------------------------

def test_multiple_overrides_same_criterion(tmp_db):
    """A reviewer who changes their mind twice gets both changes in the log."""
    analysis_id = "multi-change"
    for old, new in [(5.0, 6.0), (6.0, 4.0), (4.0, 7.0)]:
        time.sleep(0.01)
        log_override(analysis_id, "equity_access", old, new, "score", db_path=tmp_db)

    trail = get_audit_trail(analysis_id, db_path=tmp_db)
    assert len(trail) == 3

    values = [(r["old_value"], r["new_value"]) for r in trail]
    assert values == [(5.0, 6.0), (6.0, 4.0), (4.0, 7.0)]

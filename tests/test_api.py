"""Tests for POST /analyze and POST /override.

extract_evidence() is mocked so tests are fast and free — all other logic
(PDF parsing, score computation, audit logging, response shaping) runs for real.
A real PDF from data/holdout/ is uploaded to exercise the file-handling path.
"""

import os
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app, _analyses
from app.models import CRITERIA

# ---------------------------------------------------------------------------
# Fixture: deterministic fake extraction result
# ---------------------------------------------------------------------------

_FAKE_SCORES = {
    "clinical_benefit":   6,
    "safety":             5,
    "cost_effectiveness": 5,
    "budget_impact":      3,
    "equity_access":      4,
    "feasibility":        6,
}

def _fake_extraction_result() -> dict:
    result = {}
    for k, score in _FAKE_SCORES.items():
        result[k] = {
            "evidence": f"Fake evidence for {k}.",
            "citation": "Page 1",
            "suggested_score": score,
            "rationale": f"Fake rationale for {k}.",
            "confidence": "high",
        }
    result["has_conflicts"] = False
    result["_token_usage"] = {
        "input_tokens": 100,
        "output_tokens": 50,
        "chunks": 1,
        "approx_cost_usd": 0.001,
    }
    return result


# Real PDF to upload (smallest holdout; exercises the full file-upload path)
_TEST_PDF = Path("data/holdout/SR0893-Kerendia_Final.pdf")


@pytest.fixture(autouse=True)
def clear_analyses():
    """Wipe in-memory state before each test so tests don't bleed into each other."""
    _analyses.clear()
    yield
    _analyses.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def analysis_id(client, tmp_path, monkeypatch):
    """POST /analyze with a real PDF (mocked extraction) and return the analysis_id."""
    monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
    if not _TEST_PDF.exists():
        pytest.skip(f"Test PDF not found: {_TEST_PDF}")

    with patch("app.main.extract_evidence", return_value=_fake_extraction_result()):
        with open(_TEST_PDF, "rb") as f:
            resp = client.post(
                "/analyze",
                files=[("files", (str(_TEST_PDF.name), f, "application/pdf"))],
            )

    assert resp.status_code == 200, resp.text
    return resp.json()["analysis_id"]


# ---------------------------------------------------------------------------
# POST /analyze tests
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_response_shape_and_status(self, client, tmp_path, monkeypatch):
        """Full response shape check: all required keys and sub-keys present."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        if not _TEST_PDF.exists():
            pytest.skip(f"Test PDF not found: {_TEST_PDF}")

        with patch("app.main.extract_evidence", return_value=_fake_extraction_result()):
            with open(_TEST_PDF, "rb") as f:
                resp = client.post(
                    "/analyze",
                    files=[("files", (_TEST_PDF.name, f, "application/pdf"))],
                )

        assert resp.status_code == 200
        body = resp.json()

        # Top-level keys
        assert "analysis_id" in body
        assert "criteria_results" in body
        assert "current_scores" in body
        assert "current_weights" in body
        assert "initial_weighted_score" in body
        assert "has_conflicts" in body

        # All 6 criteria present
        for criterion in CRITERIA:
            assert criterion in body["criteria_results"], f"Missing criterion: {criterion}"
            cr = body["criteria_results"][criterion]
            assert "evidence" in cr
            assert "citation" in cr
            assert "suggested_score" in cr
            assert "rationale" in cr
            assert "confidence" in cr

        # Scores and weights match criteria list
        assert set(body["current_scores"].keys()) == set(CRITERIA)
        assert set(body["current_weights"].keys()) == set(CRITERIA)

        # Initial scores match fake data
        for k, expected in _FAKE_SCORES.items():
            assert body["current_scores"][k] == float(expected)

        # Weighted score is a float in [0, 1]
        ws = body["initial_weighted_score"]
        assert isinstance(ws, float)
        assert 0.0 <= ws <= 1.0

    def test_analysis_id_is_uuid(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        if not _TEST_PDF.exists():
            pytest.skip(f"Test PDF not found: {_TEST_PDF}")

        with patch("app.main.extract_evidence", return_value=_fake_extraction_result()):
            with open(_TEST_PDF, "rb") as f:
                resp = client.post(
                    "/analyze",
                    files=[("files", (_TEST_PDF.name, f, "application/pdf"))],
                )

        import uuid as _uuid
        aid = resp.json()["analysis_id"]
        _uuid.UUID(aid)  # raises ValueError if not a valid UUID

    def test_analysis_stored_in_memory(self, client, tmp_path, monkeypatch):
        """After /analyze, the state dict should contain the new analysis_id."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        if not _TEST_PDF.exists():
            pytest.skip(f"Test PDF not found: {_TEST_PDF}")

        with patch("app.main.extract_evidence", return_value=_fake_extraction_result()):
            with open(_TEST_PDF, "rb") as f:
                resp = client.post(
                    "/analyze",
                    files=[("files", (_TEST_PDF.name, f, "application/pdf"))],
                )

        aid = resp.json()["analysis_id"]
        assert aid in _analyses

    def test_no_file_returns_422(self, client):
        resp = client.post("/analyze")
        assert resp.status_code == 422

    def test_non_pdf_returns_400(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        fake = tmp_path / "not_a_pdf.txt"
        fake.write_text("hello")
        with open(fake, "rb") as f:
            resp = client.post(
                "/analyze",
                files=[("files", ("not_a_pdf.txt", f, "text/plain"))],
            )
        assert resp.status_code == 400
        assert "PDF" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# POST /override tests
# ---------------------------------------------------------------------------

class TestOverride:
    def test_score_override_updates_weighted_score(self, client, analysis_id, tmp_path, monkeypatch):
        """Overriding a score changes the weighted total."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))

        # Record the initial score for clinical_benefit
        initial_ws = client.post(
            "/analyze",  # already done via fixture; we just read from _analyses
        )
        state = _analyses[analysis_id]
        score_before = state.current_scores["clinical_benefit"]

        resp = client.post(
            "/override",
            json={
                "analysis_id": analysis_id,
                "criterion_key": "clinical_benefit",
                "field": "score",
                "new_value": 9.0,
            },
        )

        assert resp.status_code == 200
        body = resp.json()

        # Shape checks
        assert body["analysis_id"] == analysis_id
        assert body["criterion_key"] == "clinical_benefit"
        assert body["field"] == "score"
        assert body["old_value"] == score_before
        assert body["new_value"] == 9.0
        assert "updated_weighted_score" in body
        assert "audit_trail" in body

        # Weighted score is a float in [0, 1]
        ws = body["updated_weighted_score"]
        assert isinstance(ws, float)
        assert 0.0 <= ws <= 1.0

        # Score of 9 > original score, so weighted score should have increased
        state_after = _analyses[analysis_id]
        assert state_after.current_scores["clinical_benefit"] == 9.0

    def test_audit_trail_contains_override_entry(self, client, analysis_id, tmp_path, monkeypatch):
        """After one override, the audit trail has exactly one entry with correct fields."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))

        resp = client.post(
            "/override",
            json={
                "analysis_id": analysis_id,
                "criterion_key": "budget_impact",
                "field": "score",
                "new_value": 2.0,
            },
        )

        assert resp.status_code == 200
        trail = resp.json()["audit_trail"]
        assert len(trail) == 1

        entry = trail[0]
        assert entry["analysis_id"] == analysis_id
        assert entry["criterion_key"] == "budget_impact"
        assert entry["field"] == "score"
        assert entry["old_value"] == float(_FAKE_SCORES["budget_impact"])
        assert entry["new_value"] == 2.0
        assert "changed_at" in entry

    def test_two_overrides_both_appear_in_trail(self, client, analysis_id, tmp_path, monkeypatch):
        """Two consecutive overrides both appear in the audit trail, in order."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))

        client.post("/override", json={
            "analysis_id": analysis_id,
            "criterion_key": "safety",
            "field": "score",
            "new_value": 7.0,
        })
        resp = client.post("/override", json={
            "analysis_id": analysis_id,
            "criterion_key": "feasibility",
            "field": "score",
            "new_value": 8.0,
        })

        trail = resp.json()["audit_trail"]
        assert len(trail) == 2
        assert trail[0]["criterion_key"] == "safety"
        assert trail[1]["criterion_key"] == "feasibility"
        # Timestamps in ascending order
        assert trail[0]["changed_at"] <= trail[1]["changed_at"]

    def test_weight_override(self, client, analysis_id, tmp_path, monkeypatch):
        """field='weight' override is stored and recomputes the score."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))

        resp = client.post("/override", json={
            "analysis_id": analysis_id,
            "criterion_key": "clinical_benefit",
            "field": "weight",
            "new_value": 5.0,
        })

        assert resp.status_code == 200
        body = resp.json()
        assert body["field"] == "weight"
        assert body["new_value"] == 5.0
        assert 0.0 <= body["updated_weighted_score"] <= 1.0

    def test_unknown_analysis_id_returns_404(self, client):
        resp = client.post("/override", json={
            "analysis_id": "does-not-exist",
            "criterion_key": "safety",
            "field": "score",
            "new_value": 5.0,
        })
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_invalid_criterion_key_returns_422(self, client, analysis_id):
        resp = client.post("/override", json={
            "analysis_id": analysis_id,
            "criterion_key": "nonexistent_criterion",
            "field": "score",
            "new_value": 5.0,
        })
        assert resp.status_code == 422

    def test_score_out_of_range_returns_400(self, client, analysis_id):
        resp = client.post("/override", json={
            "analysis_id": analysis_id,
            "criterion_key": "safety",
            "field": "score",
            "new_value": 10.0,
        })
        assert resp.status_code == 400
        assert "1" in resp.json()["detail"] and "9" in resp.json()["detail"]

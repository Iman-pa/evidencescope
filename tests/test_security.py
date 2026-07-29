"""Tests for demo access control (X-Demo-Key) and rate limiting on POST /analyze.

DEMO_ACCESS_CODE is unset by default (see .env.example), so these are the only
tests that turn it on; every other test in this suite continues to exercise the
no-auth-required local-dev path untouched.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import matplotlib
import pytest
from fastapi.testclient import TestClient

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from app.audit import count_analyze_requests
from app.main import _analyses, app

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


@pytest.fixture(autouse=True)
def clear_analyses():
    _analyses.clear()
    yield
    _analyses.clear()


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def sample_pdf(tmp_path_factory):
    """A small real PDF with enough extractable text to pass /analyze's content check."""
    path = tmp_path_factory.mktemp("pdfs") / "sample.pdf"
    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    text = "Sample HTA report content for testing purposes. " * 20
    ax.text(0.05, 0.95, text, wrap=True, fontsize=10, va="top")
    fig.savefig(path, format="pdf")
    plt.close(fig)
    return path


def _post_analyze(client, sample_pdf, headers=None):
    with patch("app.main.extract_evidence", return_value=_fake_extraction_result()):
        with open(sample_pdf, "rb") as f:
            return client.post(
                "/analyze",
                files=[("files", (sample_pdf.name, f, "application/pdf"))],
                headers=headers or {},
            )


class TestDemoAccessControl:
    def test_missing_header_rejected_when_code_set(self, client, sample_pdf, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123")

        resp = _post_analyze(client, sample_pdf)
        assert resp.status_code == 401
        assert "demo access code" in resp.json()["detail"].lower()

    def test_wrong_header_rejected_when_code_set(self, client, sample_pdf, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123")

        resp = _post_analyze(client, sample_pdf, headers={"X-Demo-Key": "wrong"})
        assert resp.status_code == 401

    def test_correct_header_allowed_when_code_set(self, client, sample_pdf, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123")

        resp = _post_analyze(client, sample_pdf, headers={"X-Demo-Key": "secret123"})
        assert resp.status_code == 200

    def test_no_header_required_when_code_unset(self, client, sample_pdf, tmp_path, monkeypatch):
        """Local dev default: no DEMO_ACCESS_CODE means auth is skipped entirely."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)

        resp = _post_analyze(client, sample_pdf)
        assert resp.status_code == 200

    def test_env_var_whitespace_does_not_break_valid_code(self, client, sample_pdf, tmp_path, monkeypatch):
        """A trailing space/newline pasted into a dashboard env var (a common
        paste artifact) must not reject an otherwise-correct code."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123\n")

        resp = _post_analyze(client, sample_pdf, headers={"X-Demo-Key": "secret123"})
        assert resp.status_code == 200


class TestRateLimiting:
    def test_per_ip_limit_enforced(self, client, sample_pdf, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
        monkeypatch.setenv("RATE_LIMIT_PER_IP_PER_DAY", "2")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_DAY", "100")

        r1 = _post_analyze(client, sample_pdf)
        r2 = _post_analyze(client, sample_pdf)
        r3 = _post_analyze(client, sample_pdf)

        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "demo limit reached" in r3.json()["detail"].lower()

    def test_global_limit_enforced(self, client, sample_pdf, tmp_path, monkeypatch):
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
        monkeypatch.setenv("RATE_LIMIT_PER_IP_PER_DAY", "100")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_DAY", "1")

        r1 = _post_analyze(client, sample_pdf)
        r2 = _post_analyze(client, sample_pdf)

        assert r1.status_code == 200
        assert r2.status_code == 429
        assert "demo limit reached" in r2.json()["detail"].lower()

    def test_blocked_request_not_logged_again(self, client, sample_pdf, tmp_path, monkeypatch):
        """A 429-rejected request must not itself count toward the limit."""
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
        monkeypatch.setenv("RATE_LIMIT_PER_IP_PER_DAY", "1")
        monkeypatch.setenv("RATE_LIMIT_GLOBAL_PER_DAY", "100")

        _post_analyze(client, sample_pdf)
        _post_analyze(client, sample_pdf)  # blocked

        since = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert count_analyze_requests(since=since, db_path=str(db_path)) == 1


class TestAuthVerifyEndpoint:
    def test_verify_ok_when_code_unset(self, client, monkeypatch):
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
        resp = client.post("/auth/verify")
        assert resp.status_code == 200

    def test_verify_rejects_wrong_code(self, client, monkeypatch):
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123")
        resp = client.post("/auth/verify", headers={"X-Demo-Key": "wrong"})
        assert resp.status_code == 401

    def test_verify_accepts_correct_code(self, client, monkeypatch):
        monkeypatch.setenv("DEMO_ACCESS_CODE", "secret123")
        resp = client.post("/auth/verify", headers={"X-Demo-Key": "secret123"})
        assert resp.status_code == 200

    def test_verify_does_not_touch_rate_limit(self, client, sample_pdf, tmp_path, monkeypatch):
        """Calling /auth/verify repeatedly must not eat into the /analyze quota."""
        monkeypatch.setenv("AUDIT_DB_PATH", str(tmp_path / "test.db"))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)
        monkeypatch.setenv("RATE_LIMIT_PER_IP_PER_DAY", "1")

        for _ in range(5):
            client.post("/auth/verify")

        resp = _post_analyze(client, sample_pdf)
        assert resp.status_code == 200


class TestAnalyzeRequestLogging:
    def test_successful_analysis_logged_with_cost(self, client, sample_pdf, tmp_path, monkeypatch):
        db_path = tmp_path / "test.db"
        monkeypatch.setenv("AUDIT_DB_PATH", str(db_path))
        monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)

        _post_analyze(client, sample_pdf)

        since = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert count_analyze_requests(since=since, db_path=str(db_path)) == 1

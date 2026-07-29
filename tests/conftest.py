"""Shared pytest fixtures.

Ensures DEMO_ACCESS_CODE never leaks in from a developer's local .env into the
test suite — tests that specifically exercise it set it explicitly (see
test_security.py). Without this, the suite's pass/fail would depend on
ambient environment state rather than on the code being tested.
"""
import pytest


@pytest.fixture(autouse=True)
def _clear_demo_access_code(monkeypatch):
    monkeypatch.delenv("DEMO_ACCESS_CODE", raising=False)

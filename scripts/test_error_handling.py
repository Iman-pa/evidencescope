"""
Real error-handling tests — no mocks, no pytest fixtures.
Uses FastAPI TestClient against the actual app code.

Run with:
    python -X utf8 scripts/test_error_handling.py
"""
import io
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

PASS = "\u2713 PASS"
FAIL = "\u2717 FAIL"

errors = []

# ============================================================
# TEST 1: Corrupt PDF — file with .pdf extension but garbage content
# ============================================================
print("\n" + "=" * 65)
print("TEST 1: Upload a corrupt PDF (garbage bytes, .pdf extension)")
print("=" * 65)

corrupt_bytes = b"this is definitely not a valid PDF file -- just garbage bytes"
resp = client.post(
    "/analyze",
    files=[("files", ("corrupt.pdf", io.BytesIO(corrupt_bytes), "application/pdf"))],
)
print(f"  HTTP status : {resp.status_code}")
body = resp.json()
print(f"  Response    : {body}")

if resp.status_code == 400 and "detail" in body:
    print(f"  {PASS}: 400 with clean error message")
else:
    msg = f"Expected 400 with 'detail', got {resp.status_code}: {body}"
    print(f"  {FAIL}: {msg}")
    errors.append(msg)

# ============================================================
# TEST 2: Empty PDF — zero-byte file with .pdf extension
# ============================================================
print("\n" + "=" * 65)
print("TEST 2: Upload an empty PDF (0 bytes, .pdf extension)")
print("=" * 65)

resp = client.post(
    "/analyze",
    files=[("files", ("empty.pdf", io.BytesIO(b""), "application/pdf"))],
)
print(f"  HTTP status : {resp.status_code}")
body = resp.json()
print(f"  Response    : {body}")

if resp.status_code == 400 and "detail" in body:
    print(f"  {PASS}: 400 with clean error message")
else:
    msg = f"Expected 400 with 'detail', got {resp.status_code}: {body}"
    print(f"  {FAIL}: {msg}")
    errors.append(msg)

# ============================================================
# TEST 3: Invalid API key — real PDF, bad key → ExtractionError → 502
# ============================================================
print("\n" + "=" * 65)
print("TEST 3: Valid PDF + invalid API key → expect 502, no stack trace")
print("=" * 65)

pdf_path = Path("data/input/SR0893r-Kerendia_combined.pdf")
if not pdf_path.exists():
    print(f"  SKIP: {pdf_path} not found — cannot test API key failure without a PDF")
else:
    real_key = os.environ.get("ANTHROPIC_API_KEY", "")
    print(f"  Real key present: {'yes (will be restored after test)' if real_key else 'NO — .env may not be loaded'}")

    # Inject bad key
    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-INVALID-KEY-FOR-TESTING-xxxxxxxxxxx"
    print("  Injected bad key: sk-ant-INVALID-KEY-FOR-TESTING-xxx...")

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    resp = client.post(
        "/analyze",
        files=[("files", ("kerendia.pdf", io.BytesIO(pdf_bytes), "application/pdf"))],
        timeout=120,
    )
    print(f"  HTTP status : {resp.status_code}")
    body = resp.json()
    print(f"  Response    : {body}")

    # Restore real key immediately
    os.environ["ANTHROPIC_API_KEY"] = real_key
    print(f"  Real key restored.")

    has_stack_trace = "Traceback" in str(body) or "traceback" in str(body)
    if resp.status_code == 502 and "detail" in body and not has_stack_trace:
        print(f"  {PASS}: 502 with clean error message, no stack trace")
    else:
        msg = f"Expected 502 (no stack trace), got {resp.status_code}: {body}"
        print(f"  {FAIL}: {msg}")
        errors.append(msg)

# ============================================================
# TEST 4: Confirm server still healthy after key restore
# ============================================================
print("\n" + "=" * 65)
print("TEST 4: Health check after key restore")
print("=" * 65)

resp = client.get("/health")
print(f"  HTTP status : {resp.status_code}")
print(f"  Response    : {resp.json()}")
if resp.status_code == 200:
    print(f"  {PASS}: Server healthy")
else:
    msg = f"Expected 200, got {resp.status_code}"
    print(f"  {FAIL}: {msg}")
    errors.append(msg)

# ============================================================
print("\n" + "=" * 65)
if errors:
    print(f"RESULT: {len(errors)} test(s) FAILED:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("RESULT: All error-handling tests passed.")
print("=" * 65 + "\n")

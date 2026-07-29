"""Demo-mode access control and rate limiting for the public deployment.

Both checks are no-ops when DEMO_ACCESS_CODE is unset, so local development
and the existing test suite are unaffected. They only activate once
DEMO_ACCESS_CODE is set (as it is on the deployed demo).
"""

import os
from datetime import datetime, timedelta, timezone

from fastapi import Header, HTTPException, Request

from app.audit import count_analyze_requests

RATE_LIMIT_MESSAGE = (
    "Demo limit reached for today, please check back tomorrow or reach out directly."
)


def verify_demo_access(x_demo_key: str | None = Header(None, alias="X-Demo-Key")) -> None:
    """Require a matching X-Demo-Key header when DEMO_ACCESS_CODE is configured."""
    expected = os.environ.get("DEMO_ACCESS_CODE")
    if not expected:
        return
    if x_demo_key != expected:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid demo access code.",
        )


def get_client_ip(request: Request) -> str:
    """Best-effort client IP, respecting X-Forwarded-For set by Render's proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit_per_ip() -> int:
    return int(os.environ.get("RATE_LIMIT_PER_IP_PER_DAY", "5"))


def _rate_limit_global() -> int:
    return int(os.environ.get("RATE_LIMIT_GLOBAL_PER_DAY", "30"))


def enforce_rate_limits(ip: str) -> None:
    """Raise a friendly 429 if the per-IP or global rolling-24h analysis cap is hit."""
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    ip_count = count_analyze_requests(since=since, ip=ip)
    if ip_count >= _rate_limit_per_ip():
        raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)

    global_count = count_analyze_requests(since=since)
    if global_count >= _rate_limit_global():
        raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)

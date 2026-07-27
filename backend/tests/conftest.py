"""Shared pytest fixtures.

Environment variables must be set BEFORE `app.main` (and therefore
`app.config`) is imported, since settings are read once and cached.
"""
import os

os.environ.setdefault("REQUEST_TIMEOUT_SECONDS", "1")
os.environ.setdefault("MAX_CONCURRENT_AUDITS", "5")
os.environ.setdefault("CACHE_TTL_SECONDS", "300")
os.environ.setdefault("CACHE_MAX_SIZE", "100")
os.environ.setdefault("RATE_LIMIT_DEFAULT", "3/minute")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.dependencies import get_audit_cache, get_audit_service  # noqa: E402
from app.main import app  # noqa: E402
from app.rate_limiter import limiter  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    # Ensure a clean cache, rate-limit state, and freshly-configured
    # service per test so tests don't leak state into one another.
    get_audit_cache.cache_clear()
    get_audit_service.cache_clear()
    limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    get_audit_cache.cache_clear()
    get_audit_service.cache_clear()
    limiter.reset()

"""FastAPI dependency providers.

Centralizing construction here keeps routers free of instantiation logic
and makes it trivial to override dependencies in tests.
"""
from functools import lru_cache

from app.config import get_settings
from app.services.audit_service import AuditService
from app.services.cache_service import AuditCache


@lru_cache
def get_audit_cache() -> AuditCache:
    settings = get_settings()
    return AuditCache(maxsize=settings.CACHE_MAX_SIZE, ttl_seconds=settings.CACHE_TTL_SECONDS)


@lru_cache
def get_audit_service() -> AuditService:
    settings = get_settings()
    return AuditService(
        cache=get_audit_cache(),
        timeout_seconds=settings.REQUEST_TIMEOUT_SECONDS,
        max_concurrent=settings.MAX_CONCURRENT_AUDITS,
        user_agent=settings.USER_AGENT,
    )

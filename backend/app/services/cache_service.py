"""Thin, testable wrapper around a TTLCache for audit results."""
from __future__ import annotations

from typing import Optional

from cachetools import TTLCache

from app.schemas.audit import AuditData


class AuditCache:
    """A simple TTL cache keyed by the requested URL.

    Wrapped in a class (rather than using the cachetools object directly)
    so it can be swapped, mocked, or extended (e.g. metrics) without
    touching call sites, and so it can be provided via dependency injection.
    """

    def __init__(self, maxsize: int, ttl_seconds: int) -> None:
        self._store: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

    def get(self, key: str) -> Optional[AuditData]:
        return self._store.get(key)

    def set(self, key: str, value: AuditData) -> None:
        self._store[key] = value

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()

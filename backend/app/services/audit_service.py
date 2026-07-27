"""Business logic for auditing a URL.

Kept independent of FastAPI (no Request/Response objects here) so it can be
unit tested in isolation and reused from any transport layer.
"""
from __future__ import annotations

import asyncio
import html
import re
import time
from datetime import datetime, timezone

import httpx

from app.services.cache_service import AuditCache
from app.schemas.audit import AuditData
from app.utils.exceptions import AuditFailedError, AuditTimeoutError, UnreachableHostError
from app.utils.validators import validate_and_normalize_url

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_META_DESC_RE = re.compile(
    r"""<meta\s+[^>]*name=["']description["'][^>]*content=["'](.*?)["'][^>]*/?>""",
    re.IGNORECASE | re.DOTALL,
)
_META_DESC_RE_ALT = re.compile(
    r"""<meta\s+[^>]*content=["'](.*?)["'][^>]*name=["']description["'][^>]*/?>""",
    re.IGNORECASE | re.DOTALL,
)


def _extract_title(body: str) -> str | None:
    match = _TITLE_RE.search(body)
    if not match:
        return None
    return html.unescape(match.group(1)).strip() or None


def _extract_meta_description(body: str) -> str | None:
    match = _META_DESC_RE.search(body) or _META_DESC_RE_ALT.search(body)
    if not match:
        return None
    return html.unescape(match.group(1)).strip() or None


class AuditService:
    """Performs URL audits with concurrency control, timeouts, and caching."""

    def __init__(
        self,
        cache: AuditCache,
        timeout_seconds: float,
        max_concurrent: int,
        user_agent: str,
    ) -> None:
        self._cache = cache
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        # A single semaphore shared across all requests handled by this
        # service instance enforces the global concurrency ceiling.
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def audit(self, raw_url: str) -> AuditData:
        """Validate, then audit (or serve from cache) the given URL."""
        normalized_url = validate_and_normalize_url(raw_url)

        cached = self._cache.get(normalized_url)
        if cached is not None:
            return cached.model_copy(update={"cached": True})

        async with self._semaphore:
            result = await self._perform_audit(normalized_url)

        self._cache.set(normalized_url, result)
        return result

    async def _perform_audit(self, url: str) -> AuditData:
        start = time.perf_counter()
        timeout = httpx.Timeout(self._timeout_seconds)

        try:
            async with httpx.AsyncClient(
                follow_redirects=True,
                timeout=timeout,
                headers={"User-Agent": self._user_agent},
            ) as client:
                response = await client.get(url)
        except httpx.TimeoutException as exc:
            raise AuditTimeoutError(
                f"The request to {url} timed out after {self._timeout_seconds:.1f}s."
            ) from exc
        except httpx.ConnectError as exc:
            raise UnreachableHostError(f"Could not connect to host for {url}.") from exc
        except httpx.HTTPError as exc:
            raise AuditFailedError(f"Failed to audit {url}: {exc}") from exc

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        body_text = ""
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type.lower():
            # Only parse HTML bodies; avoid trying to decode binary payloads.
            body_text = response.text

        final_url = str(response.url)

        return AuditData(
            url=url,
            final_url=final_url,
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            https=final_url.lower().startswith("https://"),
            title=_extract_title(body_text) if body_text else None,
            meta_description=_extract_meta_description(body_text) if body_text else None,
            content_type=content_type or None,
            server=response.headers.get("server"),
            content_length=_resolve_content_length(response),
            timestamp=datetime.now(timezone.utc),
            cached=False,
        )


def _resolve_content_length(response: httpx.Response) -> int | None:
    header_value = response.headers.get("content-length")
    if header_value is not None:
        try:
            return int(header_value)
        except ValueError:
            pass
    try:
        return len(response.content)
    except Exception:  # pragma: no cover - defensive fallback
        return None

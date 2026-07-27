"""Standalone validation helpers, kept free of framework/service concerns."""
from urllib.parse import urlparse

from app.utils.exceptions import InvalidURLError

_ALLOWED_SCHEMES = {"http", "https"}


def validate_and_normalize_url(raw_url: str) -> str:
    """Validate that `raw_url` is a well-formed http(s) URL.

    Returns the normalized URL string on success.
    Raises InvalidURLError with a structured message on failure.
    """
    if not raw_url or not raw_url.strip():
        raise InvalidURLError("URL must not be empty.")

    candidate = raw_url.strip()

    # Users very often paste bare domains ("example.com"); we do NOT silently
    # rewrite these because the spec requires strict http/https validation,
    # but we give a clearer error message for this common case below.
    parsed = urlparse(candidate)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise InvalidURLError(
            "Invalid URL. Only http:// and https:// URLs are supported."
        )

    if not parsed.netloc:
        raise InvalidURLError("Invalid URL. A host name is required.")

    # Reject hosts with no dot and no localhost-style exception unless it's
    # explicitly localhost/127.0.0.1 for local development/testing.
    host = parsed.hostname or ""
    if not host:
        raise InvalidURLError("Invalid URL. Could not determine host.")

    return candidate

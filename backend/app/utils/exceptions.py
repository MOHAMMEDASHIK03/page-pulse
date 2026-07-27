"""Domain-specific exceptions.

Every exception carries a machine-readable `code` and a human-readable
`message` so the global exception handler can translate it into the
project's structured JSON error contract without guessing.
"""


class PagePulseError(Exception):
    """Base class for all expected, well-understood application errors."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class InvalidURLError(PagePulseError):
    code = "INVALID_URL"
    status_code = 400


class AuditTimeoutError(PagePulseError):
    code = "TIMEOUT"
    status_code = 504


class UnreachableHostError(PagePulseError):
    code = "UNREACHABLE"
    status_code = 502


class AuditFailedError(PagePulseError):
    code = "AUDIT_FAILED"
    status_code = 502

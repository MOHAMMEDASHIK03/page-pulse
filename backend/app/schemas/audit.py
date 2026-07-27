"""Request/response schemas for the audit domain."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AuditRequest(BaseModel):
    """Incoming payload for POST /api/audit."""

    url: str = Field(..., description="The URL to audit. Must be http:// or https://")

    @field_validator("url")
    @classmethod
    def strip_url(cls, value: str) -> str:
        return value.strip()


class AuditData(BaseModel):
    """The result of a successful audit."""

    url: str
    final_url: str
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    https: bool
    title: Optional[str] = None
    meta_description: Optional[str] = None
    content_type: Optional[str] = None
    server: Optional[str] = None
    content_length: Optional[int] = None
    timestamp: datetime
    cached: bool = False


class ErrorDetail(BaseModel):
    """A structured, machine-readable error payload."""

    code: str
    message: str


class AuditResponse(BaseModel):
    """Envelope returned by POST /api/audit on success."""

    success: bool = True
    data: AuditData


class ErrorResponse(BaseModel):
    """Envelope returned by any endpoint on failure."""

    success: bool = False
    error: ErrorDetail


class HealthResponse(BaseModel):
    """Envelope returned by GET /health."""

    status: str
    version: str
    uptime_seconds: float

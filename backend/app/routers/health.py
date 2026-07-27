"""Health check endpoint."""
import time

from fastapi import APIRouter

from app.config import get_settings
from app.schemas.audit import HealthResponse

router = APIRouter(tags=["health"])

_START_TIME = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Lightweight liveness/readiness probe."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.APP_VERSION,
        uptime_seconds=round(time.monotonic() - _START_TIME, 2),
    )

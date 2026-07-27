"""URL audit endpoint. No business logic here - delegates to AuditService."""
from fastapi import APIRouter, Depends, Request

from app.config import get_settings
from app.dependencies import get_audit_service
from app.rate_limiter import limiter
from app.schemas.audit import AuditRequest, AuditResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/api", tags=["audit"])
_settings = get_settings()


@router.post("/audit", response_model=AuditResponse)
@limiter.limit(_settings.RATE_LIMIT_DEFAULT)
async def audit_url(
    request: Request,
    payload: AuditRequest,
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditResponse:
    """Audit a single URL and return structured metadata about it."""
    result = await audit_service.audit(payload.url)
    request.state.cache_hit = result.cached
    return AuditResponse(success=True, data=result)

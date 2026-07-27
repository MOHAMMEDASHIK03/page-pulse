"""Middleware that assigns a request ID and emits structured JSON logs."""
from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("page_pulse.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attaches a UUID request id and logs one structured line per request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        client_ip = request.client.host if request.client else "unknown"
        error_message: str | None = None
        status_code = 500

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:  # noqa: BLE001 - re-raised after logging
            error_message = str(exc)
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            log_payload = {
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "request_id": request_id,
                "ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "response_time_ms": elapsed_ms,
                "cache_hit": getattr(request.state, "cache_hit", False),
                "error": error_message,
            }
            logger.info(json.dumps(log_payload))

        response.headers["X-Request-ID"] = request_id
        return response

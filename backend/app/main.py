"""Page Pulse API - application factory and entrypoint."""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.middleware.error_handler import register_exception_handlers
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.rate_limiter import limiter
from app.routers import audit, health

logging.basicConfig(level=logging.INFO, format="%(message)s")

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A production-grade asynchronous URL audit service.",
)

# Rate limiting (structured JSON handler for RateLimitExceeded is registered
# below via register_exception_handlers)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Structured request logging (adds X-Request-ID + JSON log line per request)
app.add_middleware(RequestLoggingMiddleware)

# Global, structured JSON error handling (overrides slowapi's default handler
# above with our own contract-conforming JSON body).
register_exception_handlers(app)

# Routers
app.include_router(health.router)
app.include_router(audit.router)


@app.get("/", tags=["root"])
async def root() -> dict:
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health",
    }

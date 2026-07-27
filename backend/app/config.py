"""
Application configuration.

All tunables are sourced from environment variables (with sane defaults)
so the service can be reconfigured per-environment without code changes.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized, typed application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # General
    APP_NAME: str = "Page Pulse"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"

    # CORS
   CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,https://silly-jalebi-36deeb.netlify.app"

    # Audit behaviour
    REQUEST_TIMEOUT_SECONDS: float = 10.0
    MAX_CONCURRENT_AUDITS: int = 5
    USER_AGENT: str = "PagePulse-Auditor/1.0 (+https://digitalheroesco.com)"

    # Cache
    CACHE_TTL_SECONDS: int = 300
    CACHE_MAX_SIZE: int = 1000

    # Rate limiting
    RATE_LIMIT_DEFAULT: str = "100/hour"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (avoids re-parsing env on every call)."""
    return Settings()

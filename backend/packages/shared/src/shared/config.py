"""Centralised application settings via pydantic-settings.

All configuration is loaded from environment variables or a .env file.
Use ``get_settings()`` to obtain a cached singleton.
"""

from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_scheduler"

    # ── Redis ─────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Worker ────────────────────────────────────────────
    WORKER_CONCURRENCY: int = 4
    SCHEDULER_ENGINE: str = "heap"  # "heap" | "timing_wheel"

    # ── Dead-Letter Queue ─────────────────────────────────
    DLQ_ALERT_THRESHOLD: int = 10
    DLQ_ALERT_EMAIL: str = "admin@dilamme.com"

    # ── SMTP (for DLQ email alerts) ───────────────────────
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ── Logging ───────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    # ── API ───────────────────────────────────────────────
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return list(json.loads(v))
        return list(v)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()

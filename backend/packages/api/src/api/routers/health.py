"""Health-check router."""

from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_redis

router = APIRouter()


@router.get("/health", summary="Health check", operation_id="health_check")
async def health_check(
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),  # type: ignore[type-arg]
) -> dict[str, str]:
    """Return connectivity status for PostgreSQL and Redis."""
    status: dict[str, str] = {"status": "ok", "database": "ok", "redis": "ok"}

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        status["database"] = f"error: {exc}"
        status["status"] = "degraded"

    try:
        await redis.ping()
    except Exception as exc:
        status["redis"] = f"error: {exc}"
        status["status"] = "degraded"

    return status

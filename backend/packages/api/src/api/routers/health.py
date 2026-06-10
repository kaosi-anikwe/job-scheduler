"""Health-check router."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_db, get_redis

router = APIRouter()


@router.get("/health", summary="Health check")
async def health_check(
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """Return connectivity status for PostgreSQL and Redis."""
    status = {"status": "ok", "database": "ok", "redis": "ok"}

    try:
        await db.execute("SELECT 1")
    except Exception as exc:
        status["database"] = f"error: {exc}"
        status["status"] = "degraded"

    try:
        await redis.ping()
    except Exception as exc:
        status["redis"] = f"error: {exc}"
        status["status"] = "degraded"

    return status

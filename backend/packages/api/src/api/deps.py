"""FastAPI dependency injection helpers."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db_session as _get_db_session
from shared.redis import get_redis as _get_redis


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an ``AsyncSession`` — commits on success, rolls back on error."""
    async for session in _get_db_session():
        yield session


async def get_redis() -> aioredis.Redis[Any]:
    """Return the shared Redis client."""
    return await _get_redis()

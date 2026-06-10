"""Redis client lifecycle management.

Provides a shared ``redis.asyncio.Redis`` connection pool and a dedicated
Pub/Sub connection for the worker cancellation listener.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.config import get_settings

# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return a shared Redis client backed by a connection pool.

    Creates the client on first call and reuses it for the process lifetime.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=20,
        )
    return _redis_client


async def get_pubsub() -> aioredis.client.PubSub:
    """Return a fresh Pub/Sub instance from the shared Redis connection pool."""
    client = await get_redis()
    return client.pubsub()


async def close_redis() -> None:
    """Close the Redis connection pool (call on shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()  # type: ignore[attr-defined]
        _redis_client = None

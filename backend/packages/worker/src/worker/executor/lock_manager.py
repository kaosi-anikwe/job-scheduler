"""Redis distributed lock manager — prevents double-allocation of jobs.

Uses atomic SET NX PX (compare-and-set) and Lua script for safe release,
per system design §6.1.
"""

from __future__ import annotations

import redis.asyncio as aioredis

from shared.logging import get_logger

logger = get_logger(__name__)

# Lua script for safe lock release: only delete if the value matches our worker UUID.
# This prevents a worker from accidentally releasing another worker's lock.
_RELEASE_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

# Lua script for safe lock extension: only extend TTL if we still own the lock.
_EXTEND_LOCK_SCRIPT = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""


class LockManager:
    """Distributed lock manager using Redis for job claim tokens."""

    def __init__(self, redis_client: aioredis.Redis) -> None:  # type: ignore[type-arg]
        self._redis = redis_client

    async def acquire(
        self,
        job_id: str,
        worker_uuid: str,
        ttl_ms: int = 30_000,
    ) -> bool:
        """Attempt to acquire an exclusive lock for a job.

        Parameters
        ----------
        job_id:
            The job to lock.
        worker_uuid:
            Unique identifier for this worker instance.
        ttl_ms:
            Lock time-to-live in milliseconds (default 30s). The lock
            auto-expires if the worker crashes without releasing it.

        Returns True if the lock was acquired, False if already held.
        """
        lock_key = f"lock:job:{job_id}"
        result = await self._redis.set(lock_key, worker_uuid, nx=True, px=ttl_ms)
        acquired = result is True

        if acquired:
            logger.debug(
                f"Lock acquired for job {job_id}",
                extra={"event": "LOCK_ACQUIRED", "job_id": job_id, "worker_node": worker_uuid},
            )

        return acquired

    async def release(self, job_id: str, worker_uuid: str) -> bool:
        """Release a lock, but only if this worker still owns it.

        Uses a Lua script for atomicity — prevents releasing another
        worker's lock if ours has already expired.

        Returns True if the lock was released, False if not owned.
        """
        lock_key = f"lock:job:{job_id}"
        result = await self._redis.eval(  # type: ignore[no-untyped-call]
            _RELEASE_LOCK_SCRIPT, 1, lock_key, worker_uuid
        )

        released = result == 1
        if released:
            logger.debug(
                f"Lock released for job {job_id}",
                extra={"event": "LOCK_RELEASED", "job_id": job_id, "worker_node": worker_uuid},
            )

        return bool(released)

    async def extend(
        self,
        job_id: str,
        worker_uuid: str,
        ttl_ms: int = 30_000,
    ) -> bool:
        """Extend the TTL of a lock (for long-running jobs).

        Only extends if this worker still owns the lock.

        Returns True if extended, False if not owned.
        """
        lock_key = f"lock:job:{job_id}"
        result = await self._redis.eval(  # type: ignore[no-untyped-call]
            _EXTEND_LOCK_SCRIPT, 1, lock_key, worker_uuid, str(ttl_ms)
        )
        return bool(result == 1)

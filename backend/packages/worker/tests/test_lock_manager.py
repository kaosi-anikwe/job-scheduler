"""Tests for the LockManager — acquire, release, extend, and contention."""

from __future__ import annotations

import fakeredis.aioredis as fakeredis  # type: ignore[import-untyped]
import pytest

from worker.executor.lock_manager import LockManager


@pytest.fixture
async def redis_client() -> fakeredis.FakeRedis:  # type: ignore[no-any-unimported]
    return fakeredis.FakeRedis()


@pytest.fixture
async def lock_manager(redis_client: fakeredis.FakeRedis) -> LockManager:  # type: ignore[no-any-unimported]
    return LockManager(redis_client)


class TestLockAcquire:
    async def test_acquire_succeeds_when_free(self, lock_manager: LockManager) -> None:
        acquired = await lock_manager.acquire("job-1", "worker-uuid-1")
        assert acquired is True

    async def test_acquire_fails_when_held_by_another_worker(
        self, lock_manager: LockManager
    ) -> None:
        await lock_manager.acquire("job-1", "worker-1")
        second = await lock_manager.acquire("job-1", "worker-2")
        assert second is False

    async def test_acquire_same_worker_fails(self, lock_manager: LockManager) -> None:
        """NX semantics: even same worker can't re-acquire without releasing."""
        await lock_manager.acquire("job-1", "worker-1")
        second = await lock_manager.acquire("job-1", "worker-1")
        assert second is False

    async def test_different_jobs_can_be_locked_simultaneously(
        self, lock_manager: LockManager
    ) -> None:
        a = await lock_manager.acquire("job-a", "worker-1")
        b = await lock_manager.acquire("job-b", "worker-1")
        assert a is True
        assert b is True


class TestLockRelease:
    async def test_release_own_lock(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire("job-1", "worker-1")
        released = await lock_manager.release("job-1", "worker-1")
        assert released is True

    async def test_release_allows_re_acquire(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire("job-1", "worker-1")
        await lock_manager.release("job-1", "worker-1")
        reacquired = await lock_manager.acquire("job-1", "worker-2")
        assert reacquired is True

    async def test_cannot_release_another_workers_lock(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire("job-1", "worker-1")
        released = await lock_manager.release("job-1", "worker-2")
        assert released is False

    async def test_release_nonexistent_lock(self, lock_manager: LockManager) -> None:
        released = await lock_manager.release("ghost", "worker-1")
        assert released is False


class TestLockExtend:
    async def test_extend_own_lock(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire("job-1", "worker-1", ttl_ms=5000)
        extended = await lock_manager.extend("job-1", "worker-1", 30_000)
        assert extended is True

    async def test_extend_another_workers_lock_fails(self, lock_manager: LockManager) -> None:
        await lock_manager.acquire("job-1", "worker-1")
        extended = await lock_manager.extend("job-1", "worker-2", 30_000)
        assert extended is False

    async def test_extend_nonexistent_lock_fails(self, lock_manager: LockManager) -> None:
        extended = await lock_manager.extend("ghost", "worker-1", 30_000)
        assert extended is False

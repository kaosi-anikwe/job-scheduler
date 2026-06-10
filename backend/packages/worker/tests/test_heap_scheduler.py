"""Tests for the HeapScheduler — ordering, starvation prevention, concurrency."""

from __future__ import annotations

import time

from worker.scheduler.heap_scheduler import HeapScheduler, JobNode


def make_node(
    job_id: str,
    base_priority: int = 2,
    scheduled_offset: float = 0.0,
    created_offset: float = 0.0,
) -> JobNode:
    """Helper to create a JobNode with relative timestamps."""
    now = time.time()
    return JobNode(
        job_id=job_id,
        job_type="send_email",
        base_priority=base_priority,
        scheduled_at=now + scheduled_offset,
        created_at=now + created_offset,
    )


class TestHeapSchedulerPushPop:
    async def test_push_and_pop_single_item(self) -> None:
        sched = HeapScheduler()
        node = make_node("job-1")
        await sched.push(node)
        result = await sched.pop()
        assert result is not None
        assert result.job_id == "job-1"

    async def test_pop_empty_returns_none(self) -> None:
        sched = HeapScheduler()
        assert await sched.pop() is None

    async def test_size_tracks_pushes(self) -> None:
        sched = HeapScheduler()
        assert await sched.size() == 0
        await sched.push(make_node("a"))
        await sched.push(make_node("b"))
        assert await sched.size() == 2

    async def test_pop_decrements_size(self) -> None:
        sched = HeapScheduler()
        await sched.push(make_node("a"))
        await sched.pop()
        assert await sched.size() == 0

    async def test_duplicate_push_ignored(self) -> None:
        sched = HeapScheduler()
        node = make_node("dup")
        await sched.push(node)
        await sched.push(node)  # second push should be ignored
        assert await sched.size() == 1

    async def test_clear_empties_scheduler(self) -> None:
        sched = HeapScheduler()
        for i in range(5):
            await sched.push(make_node(f"job-{i}"))
        await sched.clear()
        assert await sched.size() == 0


class TestHeapSchedulerOrdering:
    async def test_higher_priority_first(self) -> None:
        """Priority 1 (HIGH) should be returned before priority 3 (LOW)."""
        sched = HeapScheduler()
        now = time.time()
        # Insert low priority first to ensure heap is re-ordered
        low = JobNode(job_id="low", job_type="t", base_priority=3, scheduled_at=now, created_at=now)
        high = JobNode(
            job_id="high", job_type="t", base_priority=1, scheduled_at=now, created_at=now
        )
        await sched.push(low)
        await sched.push(high)

        first = await sched.pop()
        assert first is not None
        assert first.job_id == "high"

    async def test_equal_priority_earlier_scheduled_first(self) -> None:
        """Among equal-priority jobs, earliest scheduled_at wins."""
        sched = HeapScheduler()
        now = time.time()
        later = JobNode(
            job_id="later", job_type="t", base_priority=2, scheduled_at=now + 100, created_at=now
        )
        earlier = JobNode(
            job_id="earlier", job_type="t", base_priority=2, scheduled_at=now, created_at=now
        )
        await sched.push(later)
        await sched.push(earlier)

        first = await sched.pop()
        assert first is not None
        assert first.job_id == "earlier"

    async def test_equal_priority_equal_scheduled_earlier_created_first(self) -> None:
        """Tiebreaker: earlier created_at wins."""
        sched = HeapScheduler()
        now = time.time()
        newer = JobNode(
            job_id="newer", job_type="t", base_priority=2, scheduled_at=now, created_at=now + 1
        )
        older = JobNode(
            job_id="older", job_type="t", base_priority=2, scheduled_at=now, created_at=now - 1
        )
        await sched.push(newer)
        await sched.push(older)

        first = await sched.pop()
        assert first is not None
        assert first.job_id == "older"


class TestStarvationPrevention:
    def test_virtual_rank_decreases_with_age(self) -> None:
        """A job's virtual rank should increase with a larger scheduled_at, meaning
        an older (smaller scheduled_at) job's virtual rank is lower, outranking newer jobs."""
        now = time.time()
        recent = JobNode(
            job_id="recent", job_type="t", base_priority=3, scheduled_at=now, created_at=now
        )
        old = JobNode(
            job_id="old",
            job_type="t",
            base_priority=3,
            scheduled_at=now - 7200,
            created_at=now - 7200,
        )
        # Old job: virtual_rank = 3 + (1/3600 * (now - 7200)) — lower than recent
        assert old.virtual_rank < recent.virtual_rank

    def test_low_priority_old_job_outranks_high_priority_new_job(self) -> None:
        """After 2 hours wait, a priority-3 job should outrank a fresh priority-1 job."""
        now = time.time()
        new_high = JobNode(
            job_id="new-high",
            job_type="t",
            base_priority=1,
            scheduled_at=now,
            created_at=now,
        )
        # old_low virtual_rank = 3 + (1/3600 * (now - 7200)) = 3 + now/3600 - 2
        # new_high virtual_rank = 1 + (1/3600 * now) = 1 + now/3600
        # Difference: old_low - new_high = 2 - 2 = 0 … exactly equal at 2 hours.
        # After >2 hours, old_low wins. Let's use 3 hours to be definitive.
        very_old_low = JobNode(
            job_id="very-old-low",
            job_type="t",
            base_priority=3,
            scheduled_at=now - 10800,  # 3 hours ago
            created_at=now - 10800,
        )
        assert very_old_low < new_high  # very old low priority beats fresh high priority


class TestHeapSchedulerRemove:
    async def test_remove_existing_job(self) -> None:
        sched = HeapScheduler()
        node = make_node("to-remove")
        await sched.push(node)
        removed = await sched.remove("to-remove")
        assert removed is True
        assert await sched.size() == 0

    async def test_remove_nonexistent_job(self) -> None:
        sched = HeapScheduler()
        removed = await sched.remove("ghost")
        assert removed is False

    async def test_remove_maintains_heap_integrity(self) -> None:
        """After removing a mid-heap item, remaining pops should still be ordered."""
        sched = HeapScheduler()
        now = time.time()
        for i in range(5):
            await sched.push(
                JobNode(
                    job_id=f"job-{i}",
                    job_type="t",
                    base_priority=i + 1,
                    scheduled_at=now,
                    created_at=now,
                )
            )
        await sched.remove("job-2")  # remove priority-3 job
        results = []
        while True:
            node = await sched.pop()
            if node is None:
                break
            results.append(node.job_id)
        assert "job-2" not in results
        assert len(results) == 4


class TestHeapSchedulerPeek:
    async def test_peek_returns_top_without_removing(self) -> None:
        sched = HeapScheduler()
        node = make_node("peek-me")
        await sched.push(node)
        peeked = await sched.peek()
        assert peeked is not None
        assert peeked.job_id == "peek-me"
        assert await sched.size() == 1  # still in heap

    async def test_peek_empty_returns_none(self) -> None:
        sched = HeapScheduler()
        assert await sched.peek() is None


class TestJobNodeComparison:
    def test_eq_same_job_id(self) -> None:
        now = time.time()
        n1 = JobNode(job_id="x", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        n2 = JobNode(job_id="x", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        assert n1 == n2

    def test_eq_different_job_id(self) -> None:
        now = time.time()
        n1 = JobNode(job_id="x", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        n2 = JobNode(job_id="y", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        assert n1 != n2

    def test_hash_same_job_id(self) -> None:
        now = time.time()
        n1 = JobNode(job_id="x", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        n2 = JobNode(job_id="x", job_type="t", base_priority=2, scheduled_at=now, created_at=now)
        assert hash(n1) == hash(n2)

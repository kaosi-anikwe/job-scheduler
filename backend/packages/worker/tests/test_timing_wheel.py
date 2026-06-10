"""Tests for the HashedTimingWheel — slot assignment, tick advancement, removal."""

from __future__ import annotations

import time

from worker.scheduler.timing_wheel import HashedTimingWheel, TimingWheelJob


def make_job(job_id: str, delay: float = 0.0) -> TimingWheelJob:
    return TimingWheelJob(
        job_id=job_id,
        job_type="send_email",
        scheduled_at=time.time() + delay,
        payload={},
    )


class TestTimingWheelInsert:
    async def test_add_job_returns_slot(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        job = make_job("job-1", delay=5.0)
        slot = await wheel.add_job(job)
        assert 0 <= slot < 60

    async def test_size_after_insert(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        await wheel.add_job(make_job("a"))
        await wheel.add_job(make_job("b"))
        assert await wheel.size() == 2

    async def test_immediate_job_placed_in_current_slot(self) -> None:
        """A job scheduled for now (delay=0) goes into current_slot + 0 = current slot."""
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        job = make_job("now-job", delay=0.0)
        slot = await wheel.add_job(job)
        # With delay=0, total_ticks=0, target = (current_slot + 0) % 60 = current_slot
        assert slot == wheel.current_slot


class TestTimingWheelTick:
    async def test_tick_returns_jobs_with_zero_rounds(self) -> None:
        """Jobs placed at a slot that is one tick away should be returned on next tick."""
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        # Manually place a job in the next slot with remaining_rounds=0
        next_slot = (wheel.current_slot + 1) % wheel.num_slots
        job = TimingWheelJob(
            job_id="ready",
            job_type="t",
            scheduled_at=time.time(),
            remaining_rounds=0,
        )
        wheel.wheel[next_slot].append(job)
        wheel._job_slots["ready"] = next_slot

        ready = await wheel.tick()
        assert len(ready) == 1
        assert ready[0].job_id == "ready"

    async def test_tick_decrements_remaining_rounds(self) -> None:
        """Jobs with remaining_rounds > 0 should be decremented, not returned."""
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        next_slot = (wheel.current_slot + 1) % wheel.num_slots
        job = TimingWheelJob(
            job_id="not-ready",
            job_type="t",
            scheduled_at=time.time() + 60,
            remaining_rounds=1,
        )
        wheel.wheel[next_slot].append(job)
        wheel._job_slots["not-ready"] = next_slot

        ready = await wheel.tick()
        assert len(ready) == 0
        # remaining_rounds should now be 0
        assert wheel.wheel[next_slot][0].remaining_rounds == 0

    async def test_tick_advances_slot(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        initial_slot = wheel.current_slot
        await wheel.tick()
        assert wheel.current_slot == (initial_slot + 1) % 60

    async def test_tick_wraps_around(self) -> None:
        wheel = HashedTimingWheel(num_slots=10, tick_duration=1.0)
        wheel.current_slot = 9
        await wheel.tick()
        assert wheel.current_slot == 0


class TestTimingWheelRemove:
    async def test_remove_existing_job(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        job = make_job("remove-me", delay=5.0)
        await wheel.add_job(job)
        removed = await wheel.remove_job("remove-me")
        assert removed is True
        assert await wheel.size() == 0

    async def test_remove_nonexistent_job(self) -> None:
        wheel = HashedTimingWheel()
        removed = await wheel.remove_job("ghost")
        assert removed is False

    async def test_remove_does_not_affect_other_jobs(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        await wheel.add_job(make_job("keep", delay=5.0))
        await wheel.add_job(make_job("remove", delay=5.0))
        await wheel.remove_job("remove")
        assert await wheel.size() == 1


class TestTimingWheelClear:
    async def test_clear_empties_wheel(self) -> None:
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        for i in range(10):
            await wheel.add_job(make_job(f"job-{i}"))
        await wheel.clear()
        assert await wheel.size() == 0
        assert len(wheel._job_slots) == 0


class TestTimingWheelRoundTrip:
    async def test_long_delay_assigns_rounds(self) -> None:
        """A job scheduled 120s from now in a 60s wheel needs at least 1 remaining round.

        Due to sub-millisecond timing between job creation and add_job(),
        total_ticks may be 119 or 120, giving remaining_rounds of 1 or 2.
        We assert >= 1 to avoid flakiness.
        """
        wheel = HashedTimingWheel(num_slots=60, tick_duration=1.0)
        job = make_job("long-delay", delay=120.0)
        await wheel.add_job(job)
        slot = wheel._job_slots["long-delay"]
        found = next(j for j in wheel.wheel[slot] if j.job_id == "long-delay")
        assert found.remaining_rounds >= 1

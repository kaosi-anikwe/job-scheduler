"""Hashed Timing Wheel — alternative scheduling algorithm.

Implements the circular timing wheel. This structure
models timer events as buckets in a circular buffer, inspired by the Linux
kernel's timer infrastructure.

Design:
    - ``num_slots`` slots in a circular array (default 60)
    - ``tick_duration`` seconds per slot advance (default 1.0s)
    - Jobs map to a slot + remaining_rounds for delays > one full rotation

Tradeoffs vs. Heap:
    - O(1) insert vs. O(log n) for heap
    - O(1) tick processing (per slot) vs. O(log n) extract-min for heap
    - Less precise for very short delays (quantised to tick_duration)
    - No built-in priority ordering within a slot (FIFO per slot)
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class TimingWheelJob:
    """A job entry in the timing wheel."""

    job_id: str
    job_type: str
    scheduled_at: float  # Unix timestamp
    payload: dict[str, Any] = field(default_factory=dict)
    remaining_rounds: int = 0


class HashedTimingWheel:
    """Circular timing wheel for scheduling delayed jobs.

    Jobs are inserted into slots based on their delay from the current time.
    On each ``tick()``, the wheel advances one slot and returns all jobs in
    that slot whose ``remaining_rounds`` have reached 0.
    """

    def __init__(
        self,
        num_slots: int = 60,
        tick_duration: float = 1.0,
    ) -> None:
        self.num_slots = num_slots
        self.tick_duration = tick_duration
        self.wheel: list[list[TimingWheelJob]] = [[] for _ in range(num_slots)]
        self.current_slot = 0
        self._lock = asyncio.Lock()
        self._job_slots: dict[str, int] = {}  # job_id → slot index for O(1) removal

    async def add_job(self, job: TimingWheelJob) -> int:
        """Insert a job into the wheel.

        Calculates the target slot and remaining rounds based on the job's
        scheduled time relative to now.

        Returns the target slot index.
        """
        async with self._lock:
            current_time = time.time()
            delay = max(0.0, job.scheduled_at - current_time)
            total_ticks = int(delay / self.tick_duration)

            target_slot = (self.current_slot + total_ticks) % self.num_slots
            job.remaining_rounds = total_ticks // self.num_slots

            self.wheel[target_slot].append(job)
            self._job_slots[job.job_id] = target_slot
            return target_slot

    async def tick(self) -> list[TimingWheelJob]:
        """Advance the wheel by one slot and return ready jobs.

        Jobs whose ``remaining_rounds`` is 0 are fired. Others get
        their rounds decremented.
        """
        async with self._lock:
            self.current_slot = (self.current_slot + 1) % self.num_slots
            slot = self.wheel[self.current_slot]

            ready: list[TimingWheelJob] = []
            remaining: list[TimingWheelJob] = []

            for job in slot:
                if job.remaining_rounds <= 0:
                    ready.append(job)
                    self._job_slots.pop(job.job_id, None)
                else:
                    job.remaining_rounds -= 1
                    remaining.append(job)

            self.wheel[self.current_slot] = remaining
            return ready

    async def remove_job(self, job_id: str) -> bool:
        """Remove a specific job by ID (for cancellation)."""
        async with self._lock:
            slot_idx = self._job_slots.pop(job_id, None)
            if slot_idx is None:
                return False
            self.wheel[slot_idx] = [j for j in self.wheel[slot_idx] if j.job_id != job_id]
            return True

    async def size(self) -> int:
        """Return the total number of jobs across all slots."""
        async with self._lock:
            return sum(len(slot) for slot in self.wheel)

    async def clear(self) -> None:
        """Remove all jobs from the wheel."""
        async with self._lock:
            self.wheel = [[] for _ in range(self.num_slots)]
            self._job_slots.clear()

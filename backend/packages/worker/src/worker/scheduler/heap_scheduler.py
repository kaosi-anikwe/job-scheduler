"""Heap-based priority queue with starvation prevention.

Implements the min-heap scheduler from system design §3 with a Virtual Rank
Score that ages jobs so that lower-priority jobs eventually overtake newer
high-priority jobs.

Mathematical model (§3.1):
    V = P_base + α × scheduled_at_timestamp
    where α = 1.0 / 3600.0

A job waiting 1 hour gains a full priority tier upgrade.

3-tier sort order (§3.2):
    1. Virtual rank (lower = higher priority)
    2. Scheduled time (earlier = higher priority)
    3. Creation time (earlier = higher priority)
"""

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from typing import Any


@dataclass(order=False)
class JobNode:
    """A node in the priority heap.

    The ``__lt__`` method implements the 3-tier comparison specified in §3.2.
    """

    job_id: str
    job_type: str
    base_priority: int
    scheduled_at: float  # Unix timestamp of when the job should run
    created_at: float  # Unix timestamp of when the job was created
    payload: dict[str, Any] = field(default_factory=dict)

    # Computed on insertion — immutable for the lifetime of this heap entry
    virtual_rank: float = field(init=False)

    def __post_init__(self) -> None:
        alpha = 1.0 / 3600.0
        self.virtual_rank = float(self.base_priority) + (alpha * self.scheduled_at)

    def __lt__(self, other: JobNode) -> bool:
        # Tier 1: Virtual rank (accounts for priority + aging)
        if abs(self.virtual_rank - other.virtual_rank) >= 1e-9:
            return self.virtual_rank < other.virtual_rank
        # Tier 2: Earlier scheduled time wins
        if abs(self.scheduled_at - other.scheduled_at) >= 1e-9:
            return self.scheduled_at < other.scheduled_at
        # Tier 3: Earlier creation time wins
        return self.created_at < other.created_at

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JobNode):
            return NotImplemented
        return self.job_id == other.job_id

    def __hash__(self) -> int:
        return hash(self.job_id)


class HeapScheduler:
    """Thread-safe (asyncio-safe) min-heap priority queue for job scheduling.

    The heap only contains jobs that are *ready to run* — their scheduled
    time has arrived and all DAG dependencies are satisfied.
    """

    def __init__(self) -> None:
        self._heap: list[JobNode] = []
        self._lock = asyncio.Lock()
        self._job_ids: set[str] = set()  # Track what's in the heap to avoid duplicates

    async def push(self, node: JobNode) -> None:
        """Add a job to the heap. Ignores duplicates."""
        async with self._lock:
            if node.job_id in self._job_ids:
                return
            heapq.heappush(self._heap, node)
            self._job_ids.add(node.job_id)

    async def pop(self) -> JobNode | None:
        """Remove and return the highest-priority job, or ``None`` if empty."""
        async with self._lock:
            if not self._heap:
                return None
            node = heapq.heappop(self._heap)
            self._job_ids.discard(node.job_id)
            return node

    async def peek(self) -> JobNode | None:
        """Return the highest-priority job without removing it."""
        async with self._lock:
            return self._heap[0] if self._heap else None

    async def size(self) -> int:
        """Return the number of jobs in the heap."""
        async with self._lock:
            return len(self._heap)

    async def remove(self, job_id: str) -> bool:
        """Remove a specific job by ID (for cancellation). O(n) operation."""
        async with self._lock:
            if job_id not in self._job_ids:
                return False
            self._heap = [n for n in self._heap if n.job_id != job_id]
            heapq.heapify(self._heap)
            self._job_ids.discard(job_id)
            return True

    async def clear(self) -> None:
        """Remove all jobs from the heap."""
        async with self._lock:
            self._heap.clear()
            self._job_ids.clear()

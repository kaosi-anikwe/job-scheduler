"""Shared DAG validation utility — cycle detection for job dependency graphs.

Used by both the API (at job-creation time) and the worker (scheduler path)
so the logic lives in one canonical place inside ``shared``.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.job_dependency import JobDependency


async def validate_no_cycles(
    new_job_id: uuid.UUID,
    parent_ids: list[uuid.UUID],
    session: AsyncSession,
) -> bool:
    """Verify that adding edges ``parent → new_job_id`` doesn't create a cycle.

    Walks upward from each parent through existing dependency edges using DFS.
    If ``new_job_id`` is reachable from any proposed parent, a cycle would be
    created by the new edges.

    Returns True if the DAG remains acyclic, False if a cycle is detected.
    """
    result = await session.execute(select(JobDependency))
    edges = result.scalars().all()

    child_to_parents: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for edge in edges:
        child_to_parents[edge.child_job_id].append(edge.parent_job_id)

    for parent_id in parent_ids:
        visited: set[uuid.UUID] = set()
        stack = [parent_id]
        while stack:
            current = stack.pop()
            if current == new_job_id:
                return False  # Cycle detected
            if current in visited:
                continue
            visited.add(current)
            stack.extend(child_to_parents.get(current, []))

    return True

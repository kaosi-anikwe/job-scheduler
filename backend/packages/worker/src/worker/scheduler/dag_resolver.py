"""DAG workflow resolution — determines which jobs are ready to execute.

Uses the relational non-inclusion traversal query from system design §5.1
to find jobs whose:
1. Status is ``pending``
2. Scheduled time has arrived (``scheduled_at <= NOW()``)
3. All parent dependencies have completed

Also provides cycle detection for DAG validation.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.job import Job
from shared.models.job_dependency import JobDependency


async def get_ready_jobs(session: AsyncSession) -> list[Job]:
    """Return all jobs that are ready to be scheduled.

    A job is ready when:
    - status = 'pending'
    - scheduled_at <= NOW()
    - All parent jobs have status = 'completed' (or no parents at all)

    This implements the query.
    """
    # Raw SQL for performance on the hot path (per system design §2 guidance)
    query = text("""
        SELECT id FROM jobs
        WHERE status = 'pending'
          AND scheduled_at <= NOW()
          AND id NOT IN (
              SELECT child_job_id FROM job_dependencies
              WHERE parent_job_id IN (
                  SELECT id FROM jobs WHERE status != 'completed'
              )
          )
        ORDER BY priority ASC, scheduled_at ASC
    """)

    result = await session.execute(query)
    ready_ids = [row[0] for row in result.all()]

    if not ready_ids:
        return []

    # Fetch full ORM objects for the ready jobs
    orm_result = await session.execute(select(Job).where(Job.id.in_(ready_ids)))
    return list(orm_result.scalars().all())


async def validate_no_cycles(
    new_job_id: uuid.UUID,
    parent_ids: list[uuid.UUID],
    session: AsyncSession,
) -> bool:
    """Verify that adding edges ``parent → new_job_id`` doesn't create a cycle.

    Walks upward from each parent through existing dependency edges. If
    ``new_job_id`` is reachable from any parent, a cycle would be created.

    Returns True if the DAG remains valid, False if a cycle is detected.
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

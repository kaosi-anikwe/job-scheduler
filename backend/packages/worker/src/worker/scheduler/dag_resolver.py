"""DAG workflow resolution — determines which jobs are ready to execute.

Uses the relational non-inclusion traversal query from system design §5.1
to find jobs whose:
1. Status is ``pending``
2. Scheduled time has arrived (``scheduled_at <= NOW()``)
3. All parent dependencies have completed

Also provides cycle detection for DAG validation.
"""

from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.dag import validate_no_cycles  # re-exported; canonical impl lives in shared
from shared.models.job import Job

__all__ = ["get_ready_jobs", "validate_no_cycles"]


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

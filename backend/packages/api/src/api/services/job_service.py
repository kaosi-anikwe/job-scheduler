"""Job service — business logic for job CRUD and DAG validation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger
from shared.models.execution_log import ExecutionLogORM
from shared.models.job import JobORM
from shared.models.job_dependency import JobDependencyORM
from shared.schemas.job import (
    DashboardStats,
    JobCreate,
    JobListResponse,
    JobResponse,
)

from api.services.event_publisher import publish_event

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


async def create_job(data: JobCreate, session: AsyncSession) -> JobORM:
    """Create a new job with optional DAG dependencies.

    Validates that adding the specified dependencies does not introduce
    a cycle before committing.
    """
    job = JobORM(
        type=data.type,
        priority=data.priority.value,
        payload=data.payload,
        scheduled_at=data.scheduled_at or datetime.now(timezone.utc),
        interval=data.interval.value if data.interval else None,
    )
    session.add(job)
    await session.flush()  # Assign job.id

    # Create dependency edges
    if data.dependency_ids:
        # Validate all parent IDs exist
        result = await session.execute(
            select(JobORM.id).where(JobORM.id.in_(data.dependency_ids))
        )
        existing_ids = {row[0] for row in result.all()}
        missing = set(data.dependency_ids) - existing_ids
        if missing:
            raise ValueError(f"Parent job IDs not found: {missing}")

        # Validate no cycles
        if not await _validate_dag(job.id, data.dependency_ids, session):
            raise ValueError("Adding these dependencies would create a cycle in the DAG")

        for parent_id in data.dependency_ids:
            dep = JobDependencyORM(parent_job_id=parent_id, child_job_id=job.id)
            session.add(dep)

    # Publish creation event
    await publish_event(
        "JOB_CREATED",
        job.id,
        session,
        {"type": data.type, "priority": data.priority.value},
    )

    return job


async def get_job(job_id: uuid.UUID, session: AsyncSession) -> JobORM | None:
    """Fetch a single job by ID."""
    result = await session.execute(select(JobORM).where(JobORM.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    priority: Optional[int] = None,
    offset: int = 0,
    limit: int = 50,
) -> JobListResponse:
    """List jobs with optional filtering and pagination."""
    query = select(JobORM)
    count_query = select(func.count(JobORM.id))

    if status:
        query = query.where(JobORM.status == status)
        count_query = count_query.where(JobORM.status == status)
    if job_type:
        query = query.where(JobORM.type == job_type)
        count_query = count_query.where(JobORM.type == job_type)
    if priority is not None:
        query = query.where(JobORM.priority == priority)
        count_query = count_query.where(JobORM.priority == priority)

    query = query.order_by(JobORM.created_at.desc()).offset(offset).limit(limit)

    result = await session.execute(query)
    jobs = result.scalars().all()

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    return JobListResponse(
        jobs=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        offset=offset,
        limit=limit,
    )


async def cancel_job(
    job_id: uuid.UUID,
    session: AsyncSession,
) -> JobORM:
    """Cancel a job.

    - If ``pending``: sets status to ``cancelled``.
    - If ``processing``: sets status to ``cancelled`` and publishes a Redis
      Pub/Sub signal for the worker to cooperatively abort.
    - Otherwise: raises ValueError.
    """
    job = await get_job(job_id, session)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    if job.status not in ("pending", "processing"):
        raise ValueError(
            f"Cannot cancel job in '{job.status}' status. "
            "Only 'pending' or 'processing' jobs can be cancelled."
        )

    was_processing = job.status == "processing"
    job.status = "cancelled"

    await publish_event("JOB_CANCELLED", job.id, session)

    # If the job was processing, broadcast a cancellation signal via Redis
    if was_processing:
        from shared.redis import get_redis

        try:
            redis = await get_redis()
            await redis.publish(f"cancel:{job_id}", "cancel")
        except Exception:
            logger.warning(
                "Failed to publish cancellation signal",
                extra={"job_id": str(job_id)},
            )

    return job


async def get_dashboard_stats(session: AsyncSession) -> DashboardStats:
    """Return job counts grouped by status."""
    result = await session.execute(
        select(JobORM.status, func.count(JobORM.id))
        .group_by(JobORM.status)
    )
    counts: dict[str, int] = {row[0]: row[1] for row in result.all()}

    stats = DashboardStats(
        pending=counts.get("pending", 0),
        processing=counts.get("processing", 0),
        completed=counts.get("completed", 0),
        failed=counts.get("failed", 0),
        cancelled=counts.get("cancelled", 0),
    )
    stats.total = sum([stats.pending, stats.processing, stats.completed, stats.failed, stats.cancelled])
    return stats


async def get_job_logs(
    job_id: uuid.UUID,
    session: AsyncSession,
) -> list[ExecutionLogORM]:
    """Return execution logs for a specific job, ordered by creation time."""
    result = await session.execute(
        select(ExecutionLogORM)
        .where(ExecutionLogORM.job_id == job_id)
        .order_by(ExecutionLogORM.created_at.asc())
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# DAG validation
# ---------------------------------------------------------------------------


async def _validate_dag(
    new_job_id: uuid.UUID,
    parent_ids: list[uuid.UUID],
    session: AsyncSession,
) -> bool:
    """Check that adding edges parent→new_job_id does not create a cycle.

    Uses DFS from each parent, walking *upward* through existing parent edges,
    to verify the new_job_id is not an ancestor of any proposed parent.
    """
    # Build adjacency: child → [parents]
    result = await session.execute(select(JobDependencyORM))
    edges = result.scalars().all()

    child_to_parents: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for edge in edges:
        child_to_parents[edge.child_job_id].append(edge.parent_job_id)

    # Check: is new_job_id reachable from any parent by walking upward?
    # If so, adding parent→new_job_id would create a cycle.
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

    return True  # No cycles

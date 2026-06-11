"""Job service — business logic for job CRUD and DAG validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.services.event_publisher import publish_event
from shared.dag import validate_no_cycles
from shared.logging import get_logger
from shared.models.execution_log import ExecutionLog
from shared.models.job import Job
from shared.models.job_dependency import JobDependency
from shared.schemas.execution_log import EventType
from shared.schemas.job import (
    DashboardStats,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobStatus,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Job CRUD
# ---------------------------------------------------------------------------


async def create_job(data: JobCreate, session: AsyncSession) -> Job:
    """Create a new job with optional DAG dependencies.

    Validates that adding the specified dependencies does not introduce
    a cycle before committing.
    """
    job = Job(
        type=data.type,
        priority=data.priority.value,
        payload=data.payload,
        scheduled_at=data.scheduled_at or datetime.now(UTC),
        interval=data.interval.value if data.interval else None,
    )
    session.add(job)
    await session.flush()  # Assign job.id

    # Create dependency edges
    if data.dependency_ids:
        # Validate all parent IDs exist
        result = await session.execute(select(Job.id).where(Job.id.in_(data.dependency_ids)))
        existing_ids = {row[0] for row in result.all()}
        missing = set(data.dependency_ids) - existing_ids
        if missing:
            raise ValueError(f"Parent job IDs not found: {missing}")

        # Validate no cycles
        if not await validate_no_cycles(job.id, data.dependency_ids, session):
            raise ValueError("Adding these dependencies would create a cycle in the DAG")

        for parent_id in data.dependency_ids:
            dep = JobDependency(parent_job_id=parent_id, child_job_id=job.id)
            session.add(dep)

    # Publish creation event
    await publish_event(
        EventType.JOB_CREATED,
        job.id,
        session,
        {"type": data.type, "priority": data.priority.value},
    )

    return job


async def get_job(job_id: uuid.UUID, session: AsyncSession) -> Job | None:
    """Fetch a single job by ID."""
    result = await session.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    session: AsyncSession,
    *,
    status: str | None = None,
    job_type: str | None = None,
    priority: int | None = None,
    offset: int = 0,
    limit: int = 50,
) -> JobListResponse:
    """List jobs with optional filtering and pagination."""
    query = select(Job)
    count_query = select(func.count(Job.id))

    if status:
        query = query.where(Job.status == status)
        count_query = count_query.where(Job.status == status)
    if job_type:
        query = query.where(Job.type == job_type)
        count_query = count_query.where(Job.type == job_type)
    if priority is not None:
        query = query.where(Job.priority == priority)
        count_query = count_query.where(Job.priority == priority)

    query = query.order_by(Job.created_at.desc()).offset(offset).limit(limit)

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
) -> Job:
    """Cancel a job.

    - If ``pending``: sets status to ``cancelled``.
    - If ``processing``: sets status to ``cancelled`` and publishes a Redis
      Pub/Sub signal for the worker to cooperatively abort.
    - Otherwise: raises ValueError.
    """
    job = await get_job(job_id, session)
    if job is None:
        raise ValueError(f"Job {job_id} not found")

    if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
        raise ValueError(
            f"Cannot cancel job in '{job.status}' status. "
            "Only 'pending' or 'processing' jobs can be cancelled."
        )

    was_processing = job.status == JobStatus.PROCESSING
    job.status = JobStatus.CANCELLED

    await publish_event(EventType.JOB_CANCELLED, job.id, session)

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
    result = await session.execute(select(Job.status, func.count(Job.id)).group_by(Job.status))
    counts: dict[JobStatus, int] = {row[0]: row[1] for row in result.all()}

    stats = DashboardStats(
        pending=counts.get(JobStatus.PENDING, 0),
        processing=counts.get(JobStatus.PROCESSING, 0),
        completed=counts.get(JobStatus.COMPLETED, 0),
        failed=counts.get(JobStatus.FAILED, 0),
        cancelled=counts.get(JobStatus.CANCELLED, 0),
    )
    stats.total = sum(
        [
            stats.pending,
            stats.processing,
            stats.completed,
            stats.failed,
            stats.cancelled,
        ]
    )
    return stats


async def get_job_logs(
    job_id: uuid.UUID,
    session: AsyncSession,
) -> list[ExecutionLog]:
    """Return execution logs for a specific job, ordered by creation time."""
    result = await session.execute(
        select(ExecutionLog)
        .where(ExecutionLog.job_id == job_id)
        .order_by(ExecutionLog.created_at.asc())
    )
    return list(result.scalars().all())

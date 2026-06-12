"""Dead-Letter Queue router — list exhausted jobs and trigger manual retries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.services.event_publisher import publish_event
from shared.models.job import Job
from shared.schemas.execution_log import EventType
from shared.schemas.job import JobResponse, JobStatus

router = APIRouter()


@router.get(
    "/dlq", response_model=list[JobResponse], summary="List DLQ jobs", operation_id="list_dlq_jobs"
)
async def list_dlq_jobs(db: AsyncSession = Depends(get_db)) -> list[JobResponse]:
    """List all jobs that have exhausted their retries (dead-letter queue).

    These are jobs with ``status='failed'`` and ``retry_count >= max_retries``.
    Includes ``error_details`` for inspection.
    """
    result = await db.execute(
        select(Job)
        .where(
            Job.status == JobStatus.FAILED,
            Job.retry_count >= Job.max_retries,
        )
        .order_by(Job.updated_at.desc())
    )
    jobs = result.scalars().all()
    return [JobResponse.model_validate(j) for j in jobs]


@router.post(
    "/dlq/{job_id}/retry",
    response_model=JobResponse,
    summary="Retry a DLQ job",
    operation_id="retry_dlq_job",
)
async def retry_dlq_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> JobResponse:
    """Manually retry a job from the dead-letter queue.

    Resets ``retry_count`` to 0, ``status`` to ``pending``, and clears
    ``error_details``. The job re-enters the scheduler. If it fails again
    after exhausting retries, it returns to the DLQ.
    """
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=400,
            detail=f"Job is '{job.status}', not 'failed'. Only failed jobs can be retried.",
        )

    job.retry_count = 0
    job.status = JobStatus.PENDING
    job.error_details = None
    job.scheduled_at = datetime.now(UTC)

    await publish_event(
        EventType.JOB_RETRIED_FROM_DLQ,
        job.id,
        db,
        {"previous_retry_count": job.retry_count},
    )

    return JobResponse.model_validate(job)

"""Jobs router — CRUD, cancellation, dashboard stats, and execution logs."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.schemas.execution_log import ExecutionLogResponse
from shared.schemas.job import (
    DashboardStats,
    JobCreate,
    JobListResponse,
    JobResponse,
)

from api.deps import get_db
from api.services import job_service

router = APIRouter()


@router.post("/jobs", response_model=JobResponse, status_code=201, summary="Create a job")
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new job with optional DAG dependencies.

    If ``dependency_ids`` are provided, the job will not execute until all
    parent jobs have completed. Circular dependencies are rejected.
    """
    try:
        job = await job_service.create_job(data, db)
        return JobResponse.model_validate(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/jobs", response_model=JobListResponse, summary="List jobs")
async def list_jobs(
    status: Optional[str] = Query(None, description="Filter by status"),
    type: Optional[str] = Query(None, alias="type", description="Filter by job type"),
    priority: Optional[int] = Query(None, description="Filter by priority (1, 2, 3)"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List jobs with optional filtering and pagination."""
    return await job_service.list_jobs(
        db,
        status=status,
        job_type=type,
        priority=priority,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/jobs/dashboard/stats",
    response_model=DashboardStats,
    summary="Dashboard stats",
)
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Return job counts grouped by status for the dashboard view."""
    return await job_service.get_dashboard_stats(db)


@router.get("/jobs/{job_id}", response_model=JobResponse, summary="Get job details")
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single job by ID."""
    job = await job_service.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)


@router.patch("/jobs/{job_id}/cancel", response_model=JobResponse, summary="Cancel a job")
async def cancel_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a pending or processing job.

    If the job is currently processing, a cooperative cancellation signal
    is broadcast via Redis Pub/Sub to the worker.
    """
    try:
        job = await job_service.cancel_job(job_id, db)
        return JobResponse.model_validate(job)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get(
    "/jobs/{job_id}/logs",
    response_model=list[ExecutionLogResponse],
    summary="Get job execution logs",
)
async def get_job_logs(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get structured execution logs for a specific job."""
    # Verify job exists
    job = await job_service.get_job(job_id, db)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    logs = await job_service.get_job_logs(job_id, db)
    return [ExecutionLogResponse.model_validate(log) for log in logs]

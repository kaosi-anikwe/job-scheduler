"""Pydantic v2 schema for worker fleet status returned by the API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkerState(BaseModel):
    """Live state of a single worker bay."""

    worker_id: str = Field(..., description="Unique worker identifier")
    status: str = Field(
        default="idle",
        description="Worker status: 'idle' or 'running'",
    )
    job_id: str | None = Field(
        default=None,
        description="Job UUID this worker is currently executing, if any",
    )
    job_type: str | None = Field(
        default=None,
        description="Job type being executed, if any",
    )
    started_at: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of when the current job was started",
    )
    last_heartbeat: str | None = Field(
        default=None,
        description="ISO-8601 timestamp of last received heartbeat",
    )


class WorkerFleetStatus(BaseModel):
    """Aggregated worker fleet status."""

    workers: list[WorkerState] = Field(default_factory=list)
    total_workers: int = Field(default=0)
    busy_workers: int = Field(default=0)


class SchedulerInfo(BaseModel):
    """Information about the active scheduling algorithm."""

    engine: str = Field(
        ...,
        description="Active scheduling engine: 'heap' or 'timing_wheel'",
    )
    worker_concurrency: int = Field(
        ...,
        description="Number of worker tasks in the pool",
    )
    has_aging: bool = Field(
        ...,
        description="Whether the scheduler implements priority aging (starvation prevention)",
    )
    aging_formula: str | None = Field(
        default=None,
        description="Human-readable description of the aging formula (only when engine='heap')",
    )

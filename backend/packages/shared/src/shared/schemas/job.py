"""Pydantic v2 schemas for Job API request/response validation."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class JobStatus(StrEnum):
    """Valid job status values."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(int, Enum):
    """Priority levels: lower number = higher priority."""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


class JobInterval(StrEnum):
    """Supported recurring intervals."""

    EVERY_1_MINUTE = "every_1_minute"
    EVERY_5_MINUTES = "every_5_minutes"
    EVERY_1_HOUR = "every_1_hour"


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class JobCreate(BaseModel):
    """Schema for creating a new job."""

    type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        examples=["send_email", "webhook", "log_processing"],
    )
    priority: JobPriority = Field(
        default=JobPriority.MEDIUM,
        description="1 = High, 2 = Medium, 3 = Low",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"to": "test@gmail.com", "subject": "Welcome"}],
    )
    scheduled_at: datetime | None = Field(
        default=None,
        description="When to run. Defaults to now if omitted.",
    )
    interval: JobInterval | None = Field(
        default=None,
        description="Recurring interval. None = one-shot job.",
    )
    dependency_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="List of parent job IDs that must complete before this job runs.",
    )


class JobStatusUpdate(BaseModel):
    """Schema for updating job status (e.g. cancellation)."""

    status: JobStatus


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    """Full job representation returned by the API."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    type: str
    priority: int
    status: str
    payload: dict[str, Any]
    error_details: dict[str, Any] | None = None
    retry_count: int
    max_retries: int
    scheduled_at: datetime
    interval: str | None = None
    created_at: datetime
    updated_at: datetime


class JobListResponse(BaseModel):
    """Paginated list of jobs."""

    jobs: list[JobResponse]
    total: int
    offset: int
    limit: int


class DashboardStats(BaseModel):
    """Job counts grouped by status — for the dashboard view."""

    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0
    total: int = 0

"""Pydantic v2 schema for execution log API responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class EventType(StrEnum):
    """All possible job lifecycle event types stored in execution logs."""

    JOB_CREATED = "JOB_CREATED"
    JOB_STARTED = "JOB_STARTED"
    RETRY_ATTEMPTED = "RETRY_ATTEMPTED"
    JOB_FAILED = "JOB_FAILED"
    JOB_CANCELLED = "JOB_CANCELLED"
    JOB_COMPLETED = "JOB_COMPLETED"
    JOB_RETRIED_FROM_DLQ = "JOB_RETRIED_FROM_DLQ"
    RECURRING_SCHEDULED = "RECURRING_SCHEDULED"


class ExecutionLogResponse(BaseModel):
    """Structured log entry returned by the API."""

    model_config = {"from_attributes": True}

    id: int
    job_id: uuid.UUID
    event_type: EventType
    log_data: dict[str, Any]
    created_at: datetime

"""Pydantic v2 schema for execution log API responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ExecutionLogResponse(BaseModel):
    """Structured log entry returned by the API."""

    model_config = {"from_attributes": True}

    id: int
    job_id: uuid.UUID
    event_type: str
    log_data: dict[str, Any]
    created_at: datetime

"""Pydantic v2 schema for WebSocket event payloads.

This is the JSON shape pushed to connected frontends whenever a job
transitions state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class WebSocketEvent(BaseModel):
    """Real-time event broadcast via WebSocket."""

    event: str = Field(
        ...,
        description="Event type, e.g. JOB_CREATED, JOB_STARTED, JOB_COMPLETED",
    )
    job_id: uuid.UUID
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

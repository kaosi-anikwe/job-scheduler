"""Pydantic v2 schema for WebSocket event payloads.

This is the JSON shape pushed to connected frontends whenever a job
transitions state.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from shared.schemas.execution_log import EventType


class WebSocketEvent(BaseModel):
    """Real-time event broadcast via WebSocket."""

    event: EventType = Field(
        ...,
        description="Job lifecycle event type.",
    )
    job_id: uuid.UUID
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

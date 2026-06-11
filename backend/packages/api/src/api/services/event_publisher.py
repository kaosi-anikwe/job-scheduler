"""Event publisher — writes execution logs and broadcasts via Redis Pub/Sub.

Every job state transition is:
1. Persisted as an ``ExecutionLog`` row in Postgres.
2. Published as JSON to the ``jobs:events`` Redis channel for WebSocket fan-out.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger
from shared.models.execution_log import ExecutionLog
from shared.redis import get_redis
from shared.schemas.execution_log import EventType
from shared.schemas.websocket import WebSocketEvent

logger = get_logger(__name__)


async def publish_event(
    event_type: EventType,
    job_id: uuid.UUID,
    session: AsyncSession,
    data: dict[str, Any] | None = None,
) -> None:
    """Record an execution log and broadcast via Redis Pub/Sub.

    Parameters
    ----------
    event_type:
        The lifecycle event that occurred.
    job_id:
        The UUID of the affected job.
    session:
        Active database session (caller manages commit).
    data:
        Optional extra data to include in the log and broadcast.
    """
    log_data = data or {}

    # 1. Persist to execution_logs table
    log_entry = ExecutionLog(
        job_id=job_id,
        event_type=event_type,
        log_data=log_data,
    )
    session.add(log_entry)

    # Flush so the log entry gets an ID before we broadcast
    await session.flush()

    # 2. Broadcast to Redis Pub/Sub
    event = WebSocketEvent(
        event=event_type,
        job_id=job_id,
        data=log_data,
        timestamp=datetime.now(UTC),
    )

    try:
        redis = await get_redis()
        await redis.publish("jobs:events", event.model_dump_json())
    except Exception:
        # Redis broadcast failure should not break the API request
        logger.warning(
            "Failed to publish event to Redis",
            extra={"event": event_type, "job_id": str(job_id)},
        )

    logger.info(
        f"{event_type} for job {job_id}",
        extra={"event": event_type, "job_id": str(job_id)},
    )

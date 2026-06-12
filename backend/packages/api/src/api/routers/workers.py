"""Workers router — exposes live fleet status and scheduler configuration."""

from __future__ import annotations

import json

from fastapi import APIRouter

from shared.config import get_settings
from shared.logging import get_logger
from shared.redis import get_redis
from shared.schemas.worker import SchedulerInfo, WorkerFleetStatus, WorkerState

logger = get_logger(__name__)

router = APIRouter()


@router.get(
    "/workers",
    response_model=WorkerFleetStatus,
    summary="Worker fleet status",
    operation_id="get_worker_fleet",
)
async def get_worker_fleet() -> WorkerFleetStatus:
    """Return live status of every worker bay, read from Redis heartbeats.

    Each worker publishes a JSON blob to ``worker:heartbeat:{id}`` every 2
    seconds. This endpoint scans all matching keys and returns a snapshot.
    """
    redis = await get_redis()
    workers: list[WorkerState] = []
    busy = 0

    try:
        # Scan for all heartbeat keys
        cursor = 0
        while True:
            cursor, keys = await redis.scan(cursor, match="worker:heartbeat:*", count=100)
            for key in keys:
                raw = await redis.get(key)
                if raw is None:
                    continue
                try:
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    data = json.loads(raw)
                    state = WorkerState(
                        worker_id=data["worker_id"],
                        status=data.get("status", "idle"),
                        job_id=data.get("job_id"),
                        job_type=data.get("job_type"),
                        started_at=data.get("started_at"),
                        last_heartbeat=data.get("ts"),
                    )
                    if state.status == "running":
                        busy += 1
                    workers.append(state)
                except (json.JSONDecodeError, KeyError):
                    logger.warning(f"Malformed heartbeat key: {key}")

            if cursor == 0:
                break
    except Exception:
        logger.exception("Failed to scan worker heartbeats")

    return WorkerFleetStatus(
        workers=workers,
        total_workers=len(workers),
        busy_workers=busy,
    )


@router.get(
    "/scheduler/info",
    response_model=SchedulerInfo,
    summary="Scheduler info",
    operation_id="get_scheduler_info",
)
async def get_scheduler_info() -> SchedulerInfo:
    """Return the active scheduling algorithm and its configuration.

    The frontend uses this to determine whether priority aging (starvation
    prevention) is active and what formula is used.
    """
    settings = get_settings()
    engine = settings.SCHEDULER_ENGINE

    has_aging = engine == "heap"
    aging_formula = (
        "V = base_priority + (1.0 / 3600.0) × scheduled_at_timestamp — "
        "a job waiting 1 hour gains a full priority tier"
        if has_aging
        else None
    )

    return SchedulerInfo(
        engine=engine,
        worker_concurrency=settings.WORKER_CONCURRENCY,
        has_aging=has_aging,
        aging_formula=aging_formula,
    )

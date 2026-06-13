"""Async worker pool — consumes jobs from the scheduler and executes handlers.

Each worker task loops:
1. Pop from the scheduler (heap or timing wheel)
2. Acquire a Redis distributed lock
3. Update status to 'processing'
4. Dispatch to the appropriate handler
5. On success: mark completed, handle recurring re-scheduling
6. On failure: retry with backoff or move to DLQ
7. Release the lock

Heartbeats: each worker publishes its current state to Redis
``worker:heartbeat:{worker_id}`` every 2 seconds, so the API can surface
a live fleet view.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import get_settings
from shared.database import get_db_context
from shared.logging import get_logger
from shared.models.execution_log import ExecutionLog
from shared.models.job import Job
from shared.redis import get_redis
from shared.schemas.execution_log import EventType
from shared.schemas.job import JobStatus
from worker.executor.lock_manager import LockManager
from worker.handlers.registry import get_handler
from worker.recovery.dlq import move_to_dlq
from worker.recovery.retry import calculate_backoff, should_retry
from worker.scheduler.heap_scheduler import BaseScheduler, JobNode

logger = get_logger(__name__)

# Mapping of interval strings to timedelta
INTERVAL_MAP = {
    "every_1_minute": timedelta(minutes=1),
    "every_5_minutes": timedelta(minutes=5),
    "every_1_hour": timedelta(hours=1),
}

HEARTBEAT_INTERVAL = 2.0  # seconds between heartbeat publishes


class WorkerPool:
    """Manages a pool of concurrent async worker tasks."""

    def __init__(
        self,
        scheduler: BaseScheduler,
        lock_manager: LockManager,
        concurrency: int | None = None,
    ) -> None:
        settings = get_settings()
        self._scheduler = scheduler
        self._lock_manager = lock_manager
        self._concurrency = concurrency or settings.WORKER_CONCURRENCY
        self._tasks: list[asyncio.Task[None]] = []
        self._shutdown_event = asyncio.Event()
        # Track in-flight jobs for cooperative cancellation
        self._inflight: dict[str, asyncio.Task[Any]] = {}
        self._inflight_lock = asyncio.Lock()
        # Per-worker state for heartbeat publishing
        self._worker_states: dict[str, dict[str, Any]] = {}

    async def start(self) -> None:
        """Start the worker pool."""
        logger.info(
            f"Starting worker pool with {self._concurrency} workers",
            extra={"event": "WORKER_POOL_START"},
        )
        for i in range(self._concurrency):
            worker_id = f"worker_{i}_{uuid.uuid4().hex[:8]}"
            task = asyncio.create_task(self._worker_loop(worker_id))
            self._tasks.append(task)

    async def stop(self) -> None:
        """Gracefully shut down all workers."""
        logger.info("Shutting down worker pool", extra={"event": "WORKER_POOL_STOP"})
        self._shutdown_event.set()

        # Cancel all in-flight job tasks
        async with self._inflight_lock:
            for _job_id, task in self._inflight.items():
                task.cancel()

        # Wait for all worker loops to finish
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def cancel_job(self, job_id: str) -> bool:
        """Cooperatively cancel an in-flight job."""
        async with self._inflight_lock:
            task = self._inflight.get(job_id)
            if task:
                task.cancel()
                logger.info(
                    f"Cancellation signal sent for job {job_id}",
                    extra={"event": "JOB_CANCEL_SIGNAL", "job_id": job_id},
                )
                return True
        return False

    async def _worker_loop(self, worker_id: str) -> None:
        """Main loop for a single worker — pops jobs and processes them."""
        logger.info(f"Worker {worker_id} started", extra={"worker_node": worker_id})

        # Initialise per-worker state
        self._worker_states[worker_id] = {
            "status": "idle",
            "job_id": None,
            "job_type": None,
            "started_at": None,
        }

        # Start heartbeat publisher in background
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(worker_id))

        while not self._shutdown_event.is_set():
            try:
                node = await self._scheduler.pop()
                if node is None:
                    # No work available — back off
                    await asyncio.sleep(0.5)
                    continue

                await self._process_job(node, worker_id)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    f"Unexpected error in worker {worker_id}",
                    extra={"worker_node": worker_id},
                )
                await asyncio.sleep(1)

        heartbeat_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await heartbeat_task
        self._worker_states.pop(worker_id, None)
        logger.info(f"Worker {worker_id} stopped", extra={"worker_node": worker_id})

    async def _heartbeat_loop(self, worker_id: str) -> None:
        """Publish this worker's state to Redis every HEARTBEAT_INTERVAL."""
        redis = await get_redis()
        key = f"worker:heartbeat:{worker_id}"
        while not self._shutdown_event.is_set():
            try:
                state = self._worker_states.get(worker_id, {})
                payload = {
                    "worker_id": worker_id,
                    "status": state.get("status", "idle"),
                    "job_id": state.get("job_id"),
                    "job_type": state.get("job_type"),
                    "started_at": state.get("started_at"),
                    "ts": datetime.now(UTC).isoformat(),
                }
                await redis.setex(key, 5, json.dumps(payload))
            except Exception:
                logger.exception(f"Heartbeat publish failed for {worker_id}")
            await asyncio.sleep(HEARTBEAT_INTERVAL)

    async def _reset_to_idle(self, worker_id: str) -> None:
        """Reset worker state to idle and immediately flush to the Redis heartbeat key.

        Called before publishing any WS completion event so that when the
        browser refreshes the fleet it sees the idle state rather than a
        stale 'running' entry.
        """
        idle_state: dict[str, Any] = {
            "status": "idle",
            "job_id": None,
            "job_type": None,
            "started_at": None,
        }
        self._worker_states[worker_id] = idle_state
        try:
            redis = await get_redis()
            payload = {
                "worker_id": worker_id,
                **idle_state,
                "ts": datetime.now(UTC).isoformat(),
            }
            await redis.setex(f"worker:heartbeat:{worker_id}", 5, json.dumps(payload))
        except Exception:
            pass  # heartbeat loop will catch up within 2 s

    async def _process_job(self, node: JobNode, worker_id: str) -> None:
        """Process a single job: lock → execute → update status."""
        job_id = node.job_id

        # Update heartbeat state → running
        self._worker_states[worker_id] = {
            "status": "running",
            "job_id": job_id,
            "job_type": node.job_type,
            "started_at": datetime.now(UTC).isoformat(),
        }

        # 1. Acquire distributed lock
        if not await self._lock_manager.acquire(job_id, worker_id):
            logger.debug(
                f"Could not acquire lock for job {job_id} — skipping",
                extra={"job_id": job_id, "worker_node": worker_id},
            )
            # Reset — state was already set to 'running' before the lock attempt
            await self._reset_to_idle(worker_id)
            return

        try:
            async with get_db_context() as session:
                # 2. Load the job and update status to 'processing'
                result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
                job = result.scalar_one_or_none()

                if job is None or job.status != JobStatus.PENDING:
                    # Job was cancelled or already picked up — reset heartbeat
                    self._worker_states[worker_id] = {
                        "status": "idle",
                        "job_id": None,
                        "job_type": None,
                        "started_at": None,
                    }
                    return

                job.status = JobStatus.PROCESSING
                await self._log_event(
                    session,
                    job.id,
                    EventType.JOB_STARTED,
                    {
                        "worker_node": worker_id,
                    },
                )
                await session.commit()

            # Publish start event so the WebSocket fan-out triggers a fleet refresh
            await self._publish_redis_event(EventType.JOB_STARTED, job_id)

            # 3. Execute the handler in a tracked task
            handler = get_handler(node.job_type)
            if handler is None:
                raise ValueError(f"No handler registered for job type: {node.job_type}")

            # Create a tracked task for cooperative cancellation
            exec_task = asyncio.create_task(handler.execute(job_id, node.payload))

            async with self._inflight_lock:
                self._inflight[job_id] = exec_task

            try:
                result_data = await exec_task
            except asyncio.CancelledError:
                # Cooperative cancellation — job was cancelled while processing
                async with get_db_context() as session:
                    result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = JobStatus.CANCELLED
                        await self._log_event(
                            session,
                            job.id,
                            EventType.JOB_CANCELLED,
                            {
                                "worker_node": worker_id,
                                "reason": "cooperative_cancellation",
                            },
                        )
                    await session.commit()
                return
            finally:
                async with self._inflight_lock:
                    self._inflight.pop(job_id, None)

            # 4. Success — mark completed
            async with get_db_context() as session:
                result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
                job = result.scalar_one_or_none()
                if job:
                    job.status = JobStatus.COMPLETED
                    job.error_details = None
                    await self._log_event(
                        session,
                        job.id,
                        EventType.JOB_COMPLETED,
                        {
                            "worker_node": worker_id,
                            "result": result_data or {},
                        },
                    )

                    # Handle recurring jobs
                    if job.interval and job.interval in INTERVAL_MAP:
                        await self._schedule_next_recurrence(job, session)

                await session.commit()

            # Reset to idle BEFORE publishing the WS event so that any
            # fleet refresh triggered by that event reads the correct state.
            await self._reset_to_idle(worker_id)

            # Publish completion event via Redis
            await self._publish_redis_event(EventType.JOB_COMPLETED, job_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # 5. Failure — retry or move to DLQ
            await self._handle_failure(job_id, worker_id, exc)
        finally:
            # 6. Always release the lock
            await self._lock_manager.release(job_id, worker_id)
            # 7. Safety-net reset (covers cancelled / unexpected paths)
            await self._reset_to_idle(worker_id)

    async def _handle_failure(
        self,
        job_id: str,
        worker_id: str,
        error: Exception,
    ) -> None:
        """Handle a job execution failure: retry with backoff or move to DLQ."""
        async with get_db_context() as session:
            result = await session.execute(select(Job).where(Job.id == uuid.UUID(job_id)))
            job = result.scalar_one_or_none()
            if job is None:
                return

            job.retry_count += 1
            error_info = {
                "error": str(error),
                "error_type": type(error).__name__,
                "worker_node": worker_id,
                "attempt": job.retry_count,
            }
            job.error_details = error_info

            if should_retry(job):
                # Schedule retry with backoff
                backoff_seconds = calculate_backoff(job.retry_count)
                job.status = JobStatus.PENDING
                job.scheduled_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)

                await self._log_event(
                    session,
                    job.id,
                    EventType.RETRY_ATTEMPTED,
                    {
                        "worker_node": worker_id,
                        "attempt": job.retry_count,
                        "backoff_seconds": backoff_seconds,
                        "error": str(error),
                    },
                )

                logger.info(
                    f"Job {job_id} retry #{job.retry_count} scheduled in {backoff_seconds:.1f}s",
                    extra={"event": "RETRY_ATTEMPTED", "job_id": job_id},
                )
            else:
                # Exhausted retries — move to DLQ
                await move_to_dlq(job, error, session)
                await self._log_event(
                    session,
                    job.id,
                    EventType.JOB_FAILED,
                    {
                        "worker_node": worker_id,
                        "error": str(error),
                        "final_retry_count": job.retry_count,
                        "moved_to_dlq": True,
                    },
                )

                logger.warning(
                    f"Job {job_id} moved to DLQ after {job.retry_count} attempts",
                    extra={"event": "JOB_FAILED", "job_id": job_id},
                )

            await session.commit()

        # Reset to idle BEFORE publishing WS event (same race-condition fix as success path)
        await self._reset_to_idle(worker_id)

        # Publish failure event via Redis
        evt = EventType.JOB_FAILED if not should_retry(job) else EventType.RETRY_ATTEMPTED
        await self._publish_redis_event(evt, job_id)

    async def _schedule_next_recurrence(
        self,
        job: Job,
        session: AsyncSession,
    ) -> None:
        """Create the next instance of a recurring job."""
        interval_delta = INTERVAL_MAP.get(job.interval or "")
        if not interval_delta:
            return

        next_job = Job(
            type=job.type,
            priority=job.priority,
            payload=job.payload,
            scheduled_at=datetime.now(UTC) + interval_delta,
            interval=job.interval,
            max_retries=job.max_retries,
        )
        session.add(next_job)
        await session.flush()

        await self._log_event(
            session,
            next_job.id,
            EventType.JOB_CREATED,
            {
                "recurring_from": str(job.id),
                "interval": job.interval,
                "scheduled_at": next_job.scheduled_at.isoformat(),
            },
        )

        logger.info(
            f"Recurring job scheduled: {next_job.id} (from {job.id})",
            extra={
                "event": "RECURRING_SCHEDULED",
                "job_id": str(next_job.id),
                "parent_job_id": str(job.id),
            },
        )

    async def _log_event(
        self,
        session: AsyncSession,
        job_id: uuid.UUID,
        event_type: EventType,
        data: dict[str, Any],
    ) -> None:
        """Write an execution log entry."""
        log = ExecutionLog(
            job_id=job_id,
            event_type=event_type,
            log_data=data,
        )
        session.add(log)

    async def _publish_redis_event(self, event_type: EventType, job_id: str) -> None:
        """Publish an event to Redis for WebSocket broadcasting."""
        try:
            redis = await get_redis()
            event = json.dumps(
                {
                    "event": event_type,
                    "job_id": job_id,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            await redis.publish("jobs:events", event)
        except Exception:
            logger.warning(
                "Failed to publish Redis event",
                extra={"event": event_type, "job_id": job_id},
            )

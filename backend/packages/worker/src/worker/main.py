"""Worker entry point — orchestrates the scheduler, executor, and recovery.

Starts the following concurrent tasks:
1. Scheduler loop — polls DB, feeds ready jobs into the heap
2. Worker pool — N concurrent workers consuming from the heap
3. Cancellation listener — Redis Pub/Sub for cooperative cancellation
4. DLQ monitor — periodic threshold check with email alerting

Run with: ``uv run --package worker python -m worker.main``
"""

from __future__ import annotations

import asyncio
import contextlib
import signal

from shared.config import get_settings
from shared.database import dispose_engine, get_db_context, get_engine
from shared.logging import get_logger, setup_logging
from shared.redis import close_redis, get_redis
from worker.executor.lock_manager import LockManager
from worker.executor.worker_pool import WorkerPool
from worker.recovery.cancellation import CancellationListener
from worker.recovery.dlq import check_dlq_threshold, get_dlq_count, send_dlq_alert
from worker.scheduler.dag_resolver import get_ready_jobs
from worker.scheduler.heap_scheduler import HeapScheduler, JobNode

logger = get_logger(__name__)


async def scheduler_loop(heap: HeapScheduler, shutdown: asyncio.Event) -> None:
    """Poll the database for ready jobs and push them into the heap.

    Runs every 1 second. Only adds jobs that are:
    - pending, scheduled_at <= now, and all DAG parents completed
    - Not already in the heap
    """
    logger.info("Scheduler loop started", extra={"event": "SCHEDULER_START"})

    while not shutdown.is_set():
        try:
            async with get_db_context() as session:
                ready_jobs = await get_ready_jobs(session)

                for job in ready_jobs:
                    node = JobNode(
                        job_id=str(job.id),
                        job_type=job.type,
                        base_priority=job.priority,
                        scheduled_at=job.scheduled_at.timestamp(),
                        created_at=job.created_at.timestamp(),
                        payload=job.payload,
                    )
                    await heap.push(node)

                if ready_jobs:
                    logger.debug(
                        f"Pushed {len(ready_jobs)} jobs into heap",
                        extra={"event": "SCHEDULER_PUSH", "count": len(ready_jobs)},
                    )

        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Scheduler loop error")

        await asyncio.sleep(1.0)

    logger.info("Scheduler loop stopped", extra={"event": "SCHEDULER_STOP"})


async def dlq_monitor_loop(shutdown: asyncio.Event) -> None:
    """Periodically check the DLQ count and send alerts when threshold exceeded.

    Runs every 60 seconds.
    """
    logger.info("DLQ monitor started", extra={"event": "DLQ_MONITOR_START"})

    while not shutdown.is_set():
        try:
            async with get_db_context() as session:
                if await check_dlq_threshold(session):
                    count = await get_dlq_count(session)
                    await send_dlq_alert(count)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("DLQ monitor error")

        # Check every 60 seconds
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=60.0)
            break
        except TimeoutError:
            pass

    logger.info("DLQ monitor stopped", extra={"event": "DLQ_MONITOR_STOP"})


async def run_worker() -> None:
    """Main worker coroutine — starts all subsystems and waits for shutdown."""
    setup_logging()
    settings = get_settings()

    logger.info(
        "Worker starting",
        extra={
            "event": "WORKER_STARTING",
            "concurrency": settings.WORKER_CONCURRENCY,
            "scheduler_engine": settings.SCHEDULER_ENGINE,
        },
    )

    # Initialise infrastructure
    get_engine()
    redis = await get_redis()

    # Initialise components
    heap = HeapScheduler()
    lock_mgr = LockManager(redis)
    pool = WorkerPool(heap, lock_mgr)
    cancel_listener = CancellationListener(pool)
    shutdown = asyncio.Event()

    # Handle graceful shutdown
    def _signal_handler() -> None:
        logger.info("Shutdown signal received", extra={"event": "SHUTDOWN_SIGNAL"})
        shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _signal_handler)

    # Start all subsystems
    await pool.start()
    await cancel_listener.start()

    scheduler_task = asyncio.create_task(scheduler_loop(heap, shutdown))
    dlq_task = asyncio.create_task(dlq_monitor_loop(shutdown))

    logger.info("Worker fully started — processing jobs", extra={"event": "WORKER_READY"})

    # Wait for shutdown signal
    with contextlib.suppress(asyncio.CancelledError):
        await shutdown.wait()

    # Graceful shutdown
    logger.info("Shutting down worker...", extra={"event": "WORKER_SHUTDOWN"})

    scheduler_task.cancel()
    dlq_task.cancel()
    await cancel_listener.stop()
    await pool.stop()

    with contextlib.suppress(asyncio.CancelledError):
        await scheduler_task
    with contextlib.suppress(asyncio.CancelledError):
        await dlq_task

    # Cleanup
    await close_redis()
    await dispose_engine()

    logger.info("Worker stopped cleanly", extra={"event": "WORKER_STOPPED"})


def main() -> None:
    """CLI entry point."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_worker())


if __name__ == "__main__":
    main()

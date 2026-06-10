"""Cooperative cancellation via Redis Pub/Sub.

Subscribes to ``cancel:*`` patterns on Redis and forwards cancellation
signals to the worker pool, which cancels the matching asyncio task.
Per system design §8.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from shared.logging import get_logger
from shared.redis import get_pubsub

if TYPE_CHECKING:
    from worker.executor.worker_pool import WorkerPool

logger = get_logger(__name__)


class CancellationListener:
    """Listens for job cancellation signals on Redis Pub/Sub."""

    def __init__(self, worker_pool: WorkerPool) -> None:
        self._worker_pool = worker_pool
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start the cancellation listener as a background task."""
        self._task = asyncio.create_task(self._listen())
        logger.info("Cancellation listener started", extra={"event": "CANCEL_LISTENER_START"})

    async def stop(self) -> None:
        """Stop the cancellation listener."""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("Cancellation listener stopped", extra={"event": "CANCEL_LISTENER_STOP"})

    async def _listen(self) -> None:
        """Subscribe to cancel:* and forward signals to the worker pool."""
        try:
            pubsub = await get_pubsub()
            await pubsub.psubscribe("cancel:*")

            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    # Channel format: "cancel:{job_id}"
                    channel = message["channel"]
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")

                    job_id = channel.split(":", 1)[1] if ":" in channel else None
                    if job_id:
                        cancelled = await self._worker_pool.cancel_job(job_id)
                        if cancelled:
                            logger.info(
                                f"Job {job_id} cancellation forwarded to worker",
                                extra={"event": "CANCEL_FORWARDED", "job_id": job_id},
                            )
                        else:
                            logger.debug(
                                f"Job {job_id} not in-flight — cancellation ignored",
                                extra={"event": "CANCEL_NOT_INFLIGHT", "job_id": job_id},
                            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Cancellation listener error — restarting in 5s")
            await asyncio.sleep(5)
            self._task = asyncio.create_task(self._listen())

"""WebSocket connection manager and Redis Pub/Sub bridge.

Manages active WebSocket connections and fans out job events received
from Redis ``jobs:events`` channel to all connected clients.
"""

from __future__ import annotations

import asyncio
import contextlib

from fastapi import WebSocket, WebSocketDisconnect

from shared.logging import get_logger
from shared.redis import get_pubsub

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and Redis-bridged broadcasts."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._listener_task: asyncio.Task[None] | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(
            "WebSocket connected",
            extra={"event": "WS_CONNECTED", "total_connections": len(self._connections)},
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the registry."""
        if websocket in self._connections:
            self._connections.remove(websocket)
        logger.info(
            "WebSocket disconnected",
            extra={"event": "WS_DISCONNECTED", "total_connections": len(self._connections)},
        )

    async def broadcast(self, message: str) -> None:
        """Send a message to all connected WebSocket clients.

        Silently removes connections that have gone stale.
        """
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.disconnect(ws)

    async def start_redis_listener(self) -> None:
        """Start a background task that subscribes to Redis ``jobs:events``
        and broadcasts messages to all connected WebSocket clients.
        """
        self._listener_task = asyncio.create_task(self._redis_listener())
        logger.info("WebSocket Redis listener started")

    async def stop_redis_listener(self) -> None:
        """Cancel the Redis listener background task."""
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task
        logger.info("WebSocket Redis listener stopped")

    async def _redis_listener(self) -> None:
        """Subscribe to Redis ``jobs:events`` and fan out to WebSocket clients."""
        try:
            pubsub = await get_pubsub()
            await pubsub.subscribe("jobs:events")

            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await self.broadcast(data)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Redis listener error — will restart in 5s")
            await asyncio.sleep(5)
            # Restart the listener
            self._listener_task = asyncio.create_task(self._redis_listener())


# Module-level singleton
manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint handler — keeps connection alive and handles pings."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client can send pings or we just wait
            data = await websocket.receive_text()
            # Echo pongs for keep-alive
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

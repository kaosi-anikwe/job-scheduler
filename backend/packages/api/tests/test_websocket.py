"""Tests for the WebSocket endpoint and ConnectionManager broadcast logic."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import WebSocket

from api.websocket.manager import ConnectionManager

# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------


class TestConnectionManager:
    async def test_connect_registers_websocket(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await manager.connect(ws)
        assert ws in manager._connections

    async def test_disconnect_removes_websocket(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        await manager.connect(ws)
        manager.disconnect(ws)
        assert ws not in manager._connections

    async def test_disconnect_nonexistent_is_safe(self) -> None:
        manager = ConnectionManager()
        ws = AsyncMock(spec=WebSocket)
        manager.disconnect(ws)  # Should not raise

    async def test_broadcast_sends_to_all_connections(self) -> None:
        manager = ConnectionManager()
        ws1 = AsyncMock(spec=WebSocket)
        ws2 = AsyncMock(spec=WebSocket)
        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast('{"event": "JOB_CREATED"}')

        ws1.send_text.assert_called_once_with('{"event": "JOB_CREATED"}')
        ws2.send_text.assert_called_once_with('{"event": "JOB_CREATED"}')

    async def test_broadcast_removes_stale_connection(self) -> None:
        manager = ConnectionManager()
        good_ws = AsyncMock(spec=WebSocket)
        stale_ws = AsyncMock(spec=WebSocket)
        stale_ws.send_text.side_effect = RuntimeError("disconnected")

        await manager.connect(good_ws)
        await manager.connect(stale_ws)

        await manager.broadcast("hello")

        # Stale connection should be removed
        assert stale_ws not in manager._connections
        assert good_ws in manager._connections

    async def test_broadcast_empty_connections_is_safe(self) -> None:
        manager = ConnectionManager()
        await manager.broadcast("no clients")  # Should not raise

    async def test_start_and_stop_listener(self) -> None:
        manager = ConnectionManager()

        async def _fake_redis_listener() -> None:
            import asyncio

            await asyncio.sleep(9999)

        with patch.object(manager, "_redis_listener", side_effect=_fake_redis_listener):
            await manager.start_redis_listener()
            assert manager._listener_task is not None
            assert not manager._listener_task.done()
            await manager.stop_redis_listener()
            assert manager._listener_task.done()

    async def test_stop_listener_when_not_started_is_safe(self) -> None:
        manager = ConnectionManager()
        await manager.stop_redis_listener()  # Should not raise

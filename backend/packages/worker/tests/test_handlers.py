"""Tests for job handlers — EmailHandler, WebhookHandler, LogHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.handlers.email_handler import EmailHandler
from worker.handlers.log_handler import LogHandler
from worker.handlers.registry import get_handler, list_handlers
from worker.handlers.webhook_handler import WebhookHandler

# ---------------------------------------------------------------------------
# EmailHandler
# ---------------------------------------------------------------------------


class TestEmailHandler:
    async def test_valid_payload_succeeds(self) -> None:
        handler = EmailHandler()
        with patch("worker.handlers.email_handler.random.random", return_value=0.5):
            with patch("worker.handlers.email_handler.asyncio.sleep", new_callable=AsyncMock):
                result = await handler.execute(
                    "job-1",
                    {"to": "test@example.com", "subject": "Hello", "body": "World"},
                )
        assert result["status"] == "delivered"
        assert result["to"] == "test@example.com"

    async def test_missing_to_raises(self) -> None:
        handler = EmailHandler()
        with pytest.raises(ValueError, match="Missing required field 'to'"):
            await handler.execute("job-1", {"subject": "Hi"})

    async def test_missing_subject_raises(self) -> None:
        handler = EmailHandler()
        with pytest.raises(ValueError, match="Missing required field 'subject'"):
            await handler.execute("job-1", {"to": "test@example.com"})

    async def test_invalid_email_raises(self) -> None:
        handler = EmailHandler()
        with pytest.raises(ValueError, match="Invalid email address"):
            await handler.execute("job-1", {"to": "not-an-email", "subject": "Hi"})

    async def test_simulated_failure_raises_connection_error(self) -> None:
        handler = EmailHandler()
        with patch("worker.handlers.email_handler.random.random", return_value=0.0):
            with patch("worker.handlers.email_handler.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(ConnectionError, match="Simulated SMTP"):
                    await handler.execute(
                        "job-1",
                        {"to": "test@example.com", "subject": "Test"},
                    )

    async def test_body_defaults_to_empty_string(self) -> None:
        handler = EmailHandler()
        with patch("worker.handlers.email_handler.random.random", return_value=0.5):
            with patch("worker.handlers.email_handler.asyncio.sleep", new_callable=AsyncMock):
                result = await handler.execute(
                    "job-1",
                    {"to": "test@example.com", "subject": "No body"},
                )
        assert result["status"] == "delivered"


# ---------------------------------------------------------------------------
# WebhookHandler
# ---------------------------------------------------------------------------


class TestWebhookHandler:
    async def test_successful_post_request(self) -> None:
        handler = WebhookHandler()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"ok": true}'

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch("worker.handlers.webhook_handler.httpx.AsyncClient", return_value=mock_client):
            result = await handler.execute(
                "job-1",
                {
                    "url": "https://example.com/hook",
                    "method": "POST",
                    "headers": {"X-Custom": "value"},
                    "body": {"event": "test"},
                },
            )
        assert result["status_code"] == 200

    async def test_missing_url_raises(self) -> None:
        handler = WebhookHandler()
        with pytest.raises(ValueError, match="Missing required field 'url'"):
            await handler.execute("job-1", {"method": "POST", "headers": {}, "body": {}})

    async def test_5xx_response_raises(self) -> None:
        handler = WebhookHandler()
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service Unavailable"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.request = AsyncMock(return_value=mock_response)

        with patch("worker.handlers.webhook_handler.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ConnectionError, match="503"):
                await handler.execute(
                    "job-1",
                    {
                        "url": "https://example.com/hook",
                        "method": "POST",
                        "headers": {},
                        "body": {},
                    },
                )


# ---------------------------------------------------------------------------
# LogHandler
# ---------------------------------------------------------------------------


class TestLogHandler:
    async def test_valid_log_entries(self) -> None:
        handler = LogHandler()
        with patch("worker.handlers.log_handler.random.random", return_value=0.5):
            result = await handler.execute(
                "job-1",
                {
                    "log_entries": [
                        "INFO: server started",
                        "WARN: high memory usage",
                        "ERROR: connection refused",
                        "INFO: request processed",
                    ]
                },
            )
        assert result["total_entries"] == 4
        assert result["level_distribution"].get("INFO", 0) == 2
        assert result["level_distribution"].get("WARN", 0) == 1
        assert result["error_count"] == 1

    async def test_missing_log_entries_raises(self) -> None:
        handler = LogHandler()
        with pytest.raises(ValueError, match="Missing or invalid 'log_entries'"):
            await handler.execute("job-1", {})

    async def test_empty_log_entries_raises(self) -> None:
        """Empty list is falsy — the handler rejects it as missing."""
        handler = LogHandler()
        with pytest.raises(ValueError, match="Missing or invalid 'log_entries'"):
            await handler.execute("job-1", {"log_entries": []})

    async def test_debug_line_counted_as_parsed(self) -> None:
        handler = LogHandler()
        with patch("worker.handlers.log_handler.random.random", return_value=0.5):
            result = await handler.execute("job-1", {"log_entries": ["DEBUG: verbose output"]})
        # DEBUG matches the regex (DEBUG is in the pattern)
        assert result["total_entries"] == 1

    async def test_error_entries_collected(self) -> None:
        handler = LogHandler()
        with patch("worker.handlers.log_handler.random.random", return_value=0.5):
            result = await handler.execute(
                "job-1",
                {"log_entries": ["ERROR: disk full", "ERROR: OOM killer"]},
            )
        assert result["error_count"] == 2
        assert len(result["sample_errors"]) == 2


# ---------------------------------------------------------------------------
# Handler Registry
# ---------------------------------------------------------------------------


class TestHandlerRegistry:
    def test_all_three_handlers_registered(self) -> None:
        handlers = list_handlers()
        assert "send_email" in handlers
        assert "webhook" in handlers
        assert "log_processing" in handlers

    def test_registry_returns_correct_types(self) -> None:
        assert isinstance(get_handler("send_email"), EmailHandler)
        assert isinstance(get_handler("webhook"), WebhookHandler)
        assert isinstance(get_handler("log_processing"), LogHandler)

    def test_unknown_handler_returns_none(self) -> None:
        assert get_handler("nonexistent") is None

"""Centralised structured logging configuration.

Configures Python's ``logging`` module with JSON formatting for all log
output. Every log entry includes: timestamp, level, event, and optional
contextual fields (job_id, worker_node, correlation_id).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from shared.config import get_settings


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include extra contextual fields if present
        for field in ("event", "job_id", "worker_node", "correlation_id", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                log_entry[field] = str(value) if not isinstance(value, int | float) else value

        # Include exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_logging() -> None:
    """Configure the root logger with JSON formatting to stdout."""
    settings = get_settings()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    for name in ("sqlalchemy.engine", "asyncio", "uvicorn.access"):
        logging.getLogger(name).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)

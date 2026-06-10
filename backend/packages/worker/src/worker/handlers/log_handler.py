"""Log processing handler — parses, categorises, and aggregates log entries.

Demonstrates real data processing logic rather than just returning 200.
"""

from __future__ import annotations

import asyncio
import random
import re
from collections import Counter
from typing import Any

from shared.logging import get_logger
from worker.handlers.base import BaseHandler

logger = get_logger(__name__)

# Regex for common log line formats
LOG_PATTERN = re.compile(
    r"(?P<level>INFO|WARN|WARNING|ERROR|DEBUG|CRITICAL|FATAL)"
    r"[\s:\-]+(?P<message>.*)",
    re.IGNORECASE,
)


class LogHandler(BaseHandler):
    """Processes and aggregates log entries."""

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute log processing.

        Required payload fields:
        - ``log_entries``: list of raw log lines (strings)

        Optional:
        - ``source``: identifier for the log source
        """
        log_entries = payload.get("log_entries")
        if not log_entries or not isinstance(log_entries, list):
            raise ValueError(
                "Missing or invalid 'log_entries' in payload — expected a list of strings"
            )

        source = payload.get("source", "unknown")

        logger.info(
            f"Processing {len(log_entries)} log entries for job {job_id}",
            extra={"event": "LOG_PROCESSING", "job_id": job_id},
        )

        # -- Parse and categorise each entry --
        level_counts: Counter = Counter()
        parsed_entries: list[dict[str, str]] = []
        errors: list[str] = []

        for i, line in enumerate(log_entries):
            if not isinstance(line, str):
                continue

            # Simulate processing time per entry
            if i % 100 == 0:
                await asyncio.sleep(0.01)  # Cooperative yield

            match = LOG_PATTERN.search(line)
            if match:
                level = match.group("level").upper()
                if level == "WARNING":
                    level = "WARN"
                message = match.group("message").strip()

                level_counts[level] += 1
                parsed_entries.append({"level": level, "message": message})

                if level in ("ERROR", "CRITICAL", "FATAL"):
                    errors.append(message)
            else:
                level_counts["UNPARSED"] += 1
                parsed_entries.append({"level": "UNPARSED", "message": line.strip()})

        # -- Simulate random processing failure (~5%) --
        if random.random() < 0.05:
            raise RuntimeError(
                f"Simulated log processing failure (exercises retry logic)"
            )

        result = {
            "status": "processed",
            "source": source,
            "total_entries": len(log_entries),
            "parsed_entries": len(parsed_entries),
            "level_distribution": dict(level_counts),
            "error_count": len(errors),
            "sample_errors": errors[:5],  # First 5 errors as sample
        }

        logger.info(
            f"Log processing complete for job {job_id}: {dict(level_counts)}",
            extra={
                "event": "LOG_PROCESSED",
                "job_id": job_id,
                "total_entries": len(log_entries),
            },
        )

        return result

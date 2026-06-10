"""Email simulation handler — executes real email construction logic.

Validates payload, constructs a MIME message, simulates SMTP delivery
with realistic timing and random failures to exercise the retry system.
"""

from __future__ import annotations

import asyncio
import random
import re
from email.mime.text import MIMEText
from typing import Any

from shared.logging import get_logger
from worker.handlers.base import BaseHandler

logger = get_logger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

# Configurable failure rate for testing retry logic
SIMULATED_FAILURE_RATE = 0.10  # 10% chance of simulated SMTP failure


class EmailHandler(BaseHandler):
    """Simulates email delivery with real MIME construction and validation."""

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute email delivery simulation.

        Required payload fields:
        - ``to``: recipient email address
        - ``subject``: email subject line

        Optional:
        - ``body``: email body text (defaults to empty)
        """
        # -- Validate payload --
        to_addr = payload.get("to")
        subject = payload.get("subject")
        body = payload.get("body", "")

        if not to_addr:
            raise ValueError("Missing required field 'to' in email payload")
        if not subject:
            raise ValueError("Missing required field 'subject' in email payload")
        if not EMAIL_REGEX.match(to_addr):
            raise ValueError(f"Invalid email address: {to_addr}")

        logger.info(
            f"Processing email job {job_id}",
            extra={"event": "EMAIL_PROCESSING", "job_id": job_id},
        )

        # -- Construct MIME message (real logic, not just returning 200) --
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["To"] = to_addr
        msg["From"] = "scheduler@dilamme.com"
        msg["X-Job-ID"] = job_id

        mime_output = msg.as_string()

        # -- Simulate SMTP connection + delivery time --
        delivery_delay = random.uniform(0.5, 2.0)
        await asyncio.sleep(delivery_delay)

        # -- Simulate random failure (exercises retry logic) --
        if random.random() < SIMULATED_FAILURE_RATE:
            raise ConnectionError(
                f"Simulated SMTP connection failure for {to_addr} "
                f"(this is intentional — tests retry logic)"
            )

        logger.info(
            f"Email delivered to {to_addr}",
            extra={
                "event": "EMAIL_DELIVERED",
                "job_id": job_id,
                "to": to_addr,
                "subject": subject,
            },
        )

        return {
            "status": "delivered",
            "to": to_addr,
            "subject": subject,
            "mime_size_bytes": len(mime_output),
            "delivery_time_ms": int(delivery_delay * 1000),
        }

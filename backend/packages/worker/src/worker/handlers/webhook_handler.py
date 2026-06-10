"""Webhook delivery handler — makes real HTTP calls.

Validates the payload, sends the HTTP request via ``httpx``, and
retries on 5xx server errors.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.logging import get_logger
from worker.handlers.base import BaseHandler

logger = get_logger(__name__)


class WebhookHandler(BaseHandler):
    """Delivers webhook payloads via HTTP."""

    async def execute(self, job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Execute webhook delivery.

        Required payload fields:
        - ``url``: target URL

        Optional:
        - ``method``: HTTP method (default GET)
        - ``headers``: dict of headers
        - ``body``: request body (dict serialised as JSON)
        """
        url = payload.get("url")
        if not url:
            raise ValueError("Missing required field 'url' in webhook payload")

        method = payload.get("method", "POST").upper()
        headers = payload.get("headers", {})
        body = payload.get("body")

        logger.info(
            f"Processing webhook job {job_id}: {method} {url}",
            extra={"event": "WEBHOOK_PROCESSING", "job_id": job_id},
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
            )

        # Raise on 5xx errors (triggers retry)
        if response.status_code >= 500:
            raise ConnectionError(f"Webhook returned {response.status_code}: {response.text[:200]}")

        # 4xx errors are not retried — they're client errors
        if response.status_code >= 400:
            raise ValueError(
                f"Webhook returned client error {response.status_code}: {response.text[:200]}"
            )

        logger.info(
            f"Webhook delivered: {method} {url} → {response.status_code}",
            extra={
                "event": "WEBHOOK_DELIVERED",
                "job_id": job_id,
                "status_code": response.status_code,
            },
        )

        return {
            "status": "delivered",
            "url": url,
            "method": method,
            "status_code": response.status_code,
            "response_size_bytes": len(response.content),
        }

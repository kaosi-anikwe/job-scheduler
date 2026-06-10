"""Tests for the DLQ router — list exhausted jobs and manual retry."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient


def make_job_orm(
    *,
    job_id: uuid.UUID | None = None,
    job_type: str = "send_email",
    priority: int = 2,
    status: str = "pending",
    retry_count: int = 0,
    max_retries: int = 3,
    error_details: dict[str, Any] | None = None,
) -> MagicMock:
    now = datetime.now(UTC)
    job = MagicMock()
    job.id = job_id or uuid.uuid4()
    job.type = job_type
    job.priority = priority
    job.status = status
    job.payload = {}
    job.error_details = error_details
    job.retry_count = retry_count
    job.max_retries = max_retries
    job.scheduled_at = now
    job.interval = None
    job.created_at = now
    job.updated_at = now
    return job


# ---------------------------------------------------------------------------
# GET /api/v1/dlq
# ---------------------------------------------------------------------------


class TestListDLQ:
    async def test_empty_dlq_returns_200(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result

        resp = await client.get("/api/v1/dlq")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_dlq_returns_failed_jobs(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job = make_job_orm(
            status="failed",
            retry_count=3,
            max_retries=3,
            error_details={"message": "timeout"},
        )
        result = MagicMock()
        result.scalars.return_value.all.return_value = [job]
        mock_db.execute.return_value = result

        resp = await client.get("/api/v1/dlq")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["status"] == "failed"
        assert body[0]["error_details"]["message"] == "timeout"


# ---------------------------------------------------------------------------
# POST /api/v1/dlq/{job_id}/retry
# ---------------------------------------------------------------------------


class TestRetryDLQJob:
    async def test_retry_failed_job_succeeds(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job_id = uuid.uuid4()
        job = make_job_orm(job_id=job_id, status="failed", retry_count=3)

        # After retry, status should be pending
        def _set_pending(stmt: object) -> MagicMock:
            result = MagicMock()
            result.scalar_one_or_none.return_value = job
            return result

        mock_db.execute.side_effect = _set_pending

        with patch(
            "api.routers.dlq.publish_event",
            new_callable=AsyncMock,
        ):
            resp = await client.post(f"/api/v1/dlq/{job_id}/retry")

        assert resp.status_code == 200
        body = resp.json()
        # The router sets status='pending', retry_count=0 on the job object
        assert body["id"] == str(job_id)

    async def test_retry_nonexistent_job_returns_404(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = result

        resp = await client.post(f"/api/v1/dlq/{uuid.uuid4()}/retry")
        assert resp.status_code == 404

    async def test_retry_non_failed_job_returns_400(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        job = make_job_orm(status="pending")
        result = MagicMock()
        result.scalar_one_or_none.return_value = job
        mock_db.execute.return_value = result

        resp = await client.post(f"/api/v1/dlq/{job.id}/retry")
        assert resp.status_code == 400
        assert "pending" in resp.json()["detail"]

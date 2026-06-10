"""Tests for the jobs router — CRUD, filtering, cancellation, dashboard stats."""

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
# POST /api/v1/jobs
# ---------------------------------------------------------------------------


class TestCreateJob:
    async def test_create_minimal_job(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job = make_job_orm(job_type="send_email")

        with patch("api.services.job_service.create_job", new_callable=AsyncMock, return_value=job):
            resp = await client.post(
                "/api/v1/jobs",
                json={"type": "send_email"},
            )

        assert resp.status_code == 201
        body = resp.json()
        assert body["type"] == "send_email"
        assert body["status"] == "pending"

    async def test_create_job_with_priority(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job = make_job_orm(job_type="webhook", priority=1)

        with patch("api.services.job_service.create_job", new_callable=AsyncMock, return_value=job):
            resp = await client.post(
                "/api/v1/jobs",
                json={"type": "webhook", "priority": 1},
            )

        assert resp.status_code == 201
        assert resp.json()["priority"] == 1

    async def test_create_job_empty_type_returns_422(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/jobs", json={"type": ""})
        assert resp.status_code == 422

    async def test_create_job_with_dependency_cycle_returns_400(self, client: AsyncClient) -> None:
        with patch(
            "api.services.job_service.create_job",
            new_callable=AsyncMock,
            side_effect=ValueError("cycle"),
        ):
            resp = await client.post(
                "/api/v1/jobs",
                json={"type": "send_email", "dependency_ids": [str(uuid.uuid4())]},
            )
        assert resp.status_code == 400
        assert "cycle" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# GET /api/v1/jobs
# ---------------------------------------------------------------------------


class TestListJobs:
    async def test_list_returns_200(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        from shared.schemas.job import JobListResponse

        with patch(
            "api.services.job_service.list_jobs",
            new_callable=AsyncMock,
            return_value=JobListResponse(jobs=[], total=0, offset=0, limit=50),
        ):
            resp = await client.get("/api/v1/jobs")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["jobs"] == []

    async def test_list_with_status_filter(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        from shared.schemas.job import JobListResponse

        with patch(
            "api.services.job_service.list_jobs",
            new_callable=AsyncMock,
            return_value=JobListResponse(jobs=[], total=0, offset=0, limit=50),
        ):
            resp = await client.get("/api/v1/jobs?status=pending")

        assert resp.status_code == 200

    async def test_list_pagination_params(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        from shared.schemas.job import JobListResponse

        with patch(
            "api.services.job_service.list_jobs",
            new_callable=AsyncMock,
            return_value=JobListResponse(jobs=[], total=0, offset=10, limit=10),
        ):
            resp = await client.get("/api/v1/jobs?offset=10&limit=10")

        assert resp.status_code == 200
        assert resp.json()["offset"] == 10


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/dashboard/stats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    async def test_dashboard_stats_returns_200(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        from shared.schemas.job import DashboardStats

        with patch(
            "api.services.job_service.get_dashboard_stats",
            new_callable=AsyncMock,
            return_value=DashboardStats(pending=5, processing=2, completed=10, total=17),
        ):
            resp = await client.get("/api/v1/jobs/dashboard/stats")

        assert resp.status_code == 200
        body = resp.json()
        assert body["pending"] == 5
        assert body["completed"] == 10


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}
# ---------------------------------------------------------------------------


class TestGetJob:
    async def test_get_existing_job(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job_id = uuid.uuid4()
        job = make_job_orm(job_id=job_id)

        with patch(
            "api.services.job_service.get_job",
            new_callable=AsyncMock,
            return_value=job,
        ):
            resp = await client.get(f"/api/v1/jobs/{job_id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(job_id)

    async def test_get_nonexistent_job_returns_404(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        with patch(
            "api.services.job_service.get_job",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")

        assert resp.status_code == 404

    async def test_get_job_invalid_uuid_returns_422(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/jobs/not-a-uuid")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /api/v1/jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


class TestCancelJob:
    async def test_cancel_pending_job(self, client: AsyncClient, mock_db: AsyncMock) -> None:
        job_id = uuid.uuid4()
        job = make_job_orm(job_id=job_id, status="cancelled")

        with patch(
            "api.services.job_service.cancel_job",
            new_callable=AsyncMock,
            return_value=job,
        ):
            resp = await client.patch(f"/api/v1/jobs/{job_id}/cancel")

        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_cancel_completed_job_returns_400(
        self, client: AsyncClient, mock_db: AsyncMock
    ) -> None:
        with patch(
            "api.services.job_service.cancel_job",
            new_callable=AsyncMock,
            side_effect=ValueError("Cannot cancel a completed job"),
        ):
            resp = await client.patch(f"/api/v1/jobs/{uuid.uuid4()}/cancel")

        assert resp.status_code == 400
        assert "Cannot cancel" in resp.json()["detail"]

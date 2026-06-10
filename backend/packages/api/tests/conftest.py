"""Shared fixtures for API tests.

Uses httpx.AsyncClient with overridden dependencies so tests run without
a real Postgres or Redis connection.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.main import create_app

# ---------------------------------------------------------------------------
# Minimal Job stub that behaves like the ORM model
# ---------------------------------------------------------------------------


def make_job_orm(
    *,
    job_id: uuid.UUID | None = None,
    job_type: str = "send_email",
    priority: int = 2,
    status: str = "pending",
    retry_count: int = 0,
    max_retries: int = 3,
    error_details: dict[str, Any] | None = None,
    interval: str | None = None,
) -> MagicMock:
    """Return a MagicMock that satisfies model_validate(job)."""
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
    job.interval = interval
    job.created_at = now
    job.updated_at = now
    return job


# Expose as a pytest fixture (callable factory)
@pytest.fixture
def job_factory() -> Any:
    return make_job_orm


# ---------------------------------------------------------------------------
# Async DB session mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock AsyncSession — can be configured per test."""
    session = AsyncMock(spec=AsyncSession)
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# HTTP test client with dependency overrides
# ---------------------------------------------------------------------------


@pytest.fixture
async def client(mock_db: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client with DB dependency overridden."""
    app = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield mock_db  # type: ignore[misc]

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

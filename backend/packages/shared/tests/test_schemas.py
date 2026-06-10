"""Tests for shared Pydantic schemas — serialisation, validation, edge cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shared.schemas.execution_log import ExecutionLogResponse
from shared.schemas.job import (
    DashboardStats,
    JobCreate,
    JobInterval,
    JobListResponse,
    JobPriority,
    JobResponse,
    JobStatus,
    JobStatusUpdate,
)

# ---------------------------------------------------------------------------
# JobCreate
# ---------------------------------------------------------------------------


class TestJobCreate:
    def test_minimal_valid(self) -> None:
        job = JobCreate(type="send_email")
        assert job.type == "send_email"
        assert job.priority == JobPriority.MEDIUM
        assert job.payload == {}
        assert job.scheduled_at is None
        assert job.interval is None
        assert job.dependency_ids == []

    def test_full_valid(self) -> None:
        dep_id = uuid.uuid4()
        now = datetime.now(UTC)
        job = JobCreate(
            type="webhook",
            priority=JobPriority.HIGH,
            payload={"url": "https://example.com"},
            scheduled_at=now,
            interval=JobInterval.EVERY_1_HOUR,
            dependency_ids=[dep_id],
        )
        assert job.priority == JobPriority.HIGH
        assert job.interval == JobInterval.EVERY_1_HOUR
        assert dep_id in job.dependency_ids

    def test_type_empty_string_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JobCreate(type="")

    def test_type_too_long_rejected(self) -> None:
        with pytest.raises(ValidationError):
            JobCreate(type="x" * 51)

    def test_type_max_length_accepted(self) -> None:
        job = JobCreate(type="x" * 50)
        assert len(job.type) == 50

    def test_dependency_ids_default_empty(self) -> None:
        job = JobCreate(type="log_processing")
        assert job.dependency_ids == []

    def test_multiple_dependency_ids(self) -> None:
        ids = [uuid.uuid4() for _ in range(3)]
        job = JobCreate(type="log_processing", dependency_ids=ids)
        assert len(job.dependency_ids) == 3


# ---------------------------------------------------------------------------
# JobStatus enum
# ---------------------------------------------------------------------------


class TestJobStatus:
    def test_all_values(self) -> None:
        assert JobStatus.PENDING == "pending"
        assert JobStatus.PROCESSING == "processing"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"

    def test_str_enum_is_string(self) -> None:
        assert isinstance(JobStatus.PENDING, str)


# ---------------------------------------------------------------------------
# JobInterval enum
# ---------------------------------------------------------------------------


class TestJobInterval:
    def test_all_values(self) -> None:
        assert JobInterval.EVERY_1_MINUTE == "every_1_minute"
        assert JobInterval.EVERY_5_MINUTES == "every_5_minutes"
        assert JobInterval.EVERY_1_HOUR == "every_1_hour"


# ---------------------------------------------------------------------------
# JobResponse (from_attributes)
# ---------------------------------------------------------------------------


class TestJobResponse:
    def test_serialise_from_dict(self) -> None:
        now = datetime.now(UTC)
        resp = JobResponse(
            id=uuid.uuid4(),
            type="send_email",
            priority=2,
            status="pending",
            payload={"to": "a@b.com"},
            error_details=None,
            retry_count=0,
            max_retries=3,
            scheduled_at=now,
            interval=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.status == "pending"
        assert resp.error_details is None

    def test_error_details_populated(self) -> None:
        now = datetime.now(UTC)
        resp = JobResponse(
            id=uuid.uuid4(),
            type="webhook",
            priority=1,
            status="failed",
            payload={},
            error_details={"message": "timeout", "traceback": "..."},
            retry_count=3,
            max_retries=3,
            scheduled_at=now,
            interval=None,
            created_at=now,
            updated_at=now,
        )
        assert resp.error_details is not None
        assert resp.error_details["message"] == "timeout"


# ---------------------------------------------------------------------------
# JobStatusUpdate
# ---------------------------------------------------------------------------


class TestJobStatusUpdate:
    def test_valid_cancelled(self) -> None:
        upd = JobStatusUpdate(status=JobStatus.CANCELLED)
        assert upd.status == JobStatus.CANCELLED

    def test_invalid_status_string(self) -> None:
        with pytest.raises(ValidationError):
            JobStatusUpdate(status="unknown")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# DashboardStats
# ---------------------------------------------------------------------------


class TestDashboardStats:
    def test_defaults_zero(self) -> None:
        stats = DashboardStats()
        assert stats.pending == 0
        assert stats.processing == 0
        assert stats.completed == 0
        assert stats.failed == 0
        assert stats.cancelled == 0
        assert stats.total == 0

    def test_custom_values(self) -> None:
        stats = DashboardStats(pending=5, processing=2, completed=10, failed=1, total=18)
        assert stats.pending == 5
        assert stats.total == 18


# ---------------------------------------------------------------------------
# JobListResponse
# ---------------------------------------------------------------------------


class TestJobListResponse:
    def test_empty_list(self) -> None:
        resp = JobListResponse(jobs=[], total=0, offset=0, limit=50)
        assert resp.jobs == []
        assert resp.total == 0


# ---------------------------------------------------------------------------
# ExecutionLogResponse
# ---------------------------------------------------------------------------


class TestExecutionLogResponse:
    def test_valid(self) -> None:
        now = datetime.now(UTC)
        resp = ExecutionLogResponse(
            id=1,
            job_id=uuid.uuid4(),
            event_type="JOB_STARTED",
            log_data={"worker_node": "w1"},
            created_at=now,
        )
        assert resp.event_type == "JOB_STARTED"
        assert resp.log_data["worker_node"] == "w1"

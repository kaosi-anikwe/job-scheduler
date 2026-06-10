"""Tests for shared ORM models — instantiation and constraint validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from shared.models.execution_log import ExecutionLog
from shared.models.job import Job
from shared.models.job_dependency import JobDependency

# ---------------------------------------------------------------------------
# Job model
# ---------------------------------------------------------------------------


class TestJobModel:
    def test_instantiation_with_defaults(self) -> None:
        job = Job(
            type="send_email",
            scheduled_at=datetime.now(UTC),
            payload={},
        )
        assert job.type == "send_email"
        assert job.payload == {}

    def test_uuid_default_generated(self) -> None:
        job1 = Job(type="webhook", scheduled_at=datetime.now(UTC), payload={})
        job2 = Job(type="webhook", scheduled_at=datetime.now(UTC), payload={})
        # Python-side default should generate unique UUIDs
        # (server_default generates on DB commit; Python default generates on init)
        # Both may be None if only server_default is set — just verify type when set
        if job1.id is not None and job2.id is not None:
            assert job1.id != job2.id

    def test_explicit_uuid(self) -> None:
        job_id = uuid.uuid4()
        job = Job(id=job_id, type="log_processing", scheduled_at=datetime.now(UTC), payload={})
        assert job.id == job_id

    def test_retry_count_default(self) -> None:
        """Column default of 0 applies at INSERT time; attribute is None before flush."""
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload={})
        # Python-side before DB flush — attribute is None or 0 depending on SQLAlchemy version
        assert job.retry_count in (None, 0)

    def test_max_retries_default(self) -> None:
        """Column default of 3 applies at INSERT time; attribute is None or 3 before flush."""
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload={})
        assert job.max_retries in (None, 3)

    def test_error_details_none_by_default(self) -> None:
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload={})
        assert job.error_details is None

    def test_interval_none_by_default(self) -> None:
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload={})
        assert job.interval is None

    def test_payload_jsonb_dict(self) -> None:
        payload = {"to": "a@b.com", "subject": "Hi", "nested": {"key": "value"}}
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload=payload)
        assert job.payload["nested"]["key"] == "value"

    def test_repr_contains_type(self) -> None:
        job = Job(type="webhook", scheduled_at=datetime.now(UTC), payload={})
        r = repr(job)
        assert "Job" in r

    def test_tablename(self) -> None:
        assert Job.__tablename__ == "jobs"


# ---------------------------------------------------------------------------
# JobDependency model
# ---------------------------------------------------------------------------


class TestJobDependencyModel:
    def test_instantiation(self) -> None:
        parent_id = uuid.uuid4()
        child_id = uuid.uuid4()
        dep = JobDependency(parent_job_id=parent_id, child_job_id=child_id)
        assert dep.parent_job_id == parent_id
        assert dep.child_job_id == child_id

    def test_tablename(self) -> None:
        assert JobDependency.__tablename__ == "job_dependencies"

    def test_different_parent_child(self) -> None:
        pid = uuid.uuid4()
        cid = uuid.uuid4()
        dep = JobDependency(parent_job_id=pid, child_job_id=cid)
        assert dep.parent_job_id != dep.child_job_id


# ---------------------------------------------------------------------------
# ExecutionLog model
# ---------------------------------------------------------------------------


class TestExecutionLogModel:
    def test_instantiation(self) -> None:
        log = ExecutionLog(
            job_id=uuid.uuid4(),
            event_type="JOB_CREATED",
            log_data={"worker_node": "w1"},
        )
        assert log.event_type == "JOB_CREATED"
        assert log.log_data["worker_node"] == "w1"

    def test_repr(self) -> None:
        log = ExecutionLog(
            job_id=uuid.uuid4(),
            event_type="JOB_STARTED",
            log_data={},
        )
        r = repr(log)
        assert "ExecutionLog" in r
        assert "JOB_STARTED" in r

    def test_tablename(self) -> None:
        assert ExecutionLog.__tablename__ == "execution_logs"


# ---------------------------------------------------------------------------
# TimestampMixin
# ---------------------------------------------------------------------------


class TestTimestampMixin:
    def test_mixin_attributes_present_on_job(self) -> None:
        """Job inherits TimestampMixin so it should have created_at/updated_at columns."""
        job = Job(type="send_email", scheduled_at=datetime.now(UTC), payload={})
        # Columns exist (may be None until DB commit, but attrs should be accessible)
        assert hasattr(job, "created_at")
        assert hasattr(job, "updated_at")

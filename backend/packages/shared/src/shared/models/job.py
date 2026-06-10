"""Job ORM model — the central entity of the scheduler.

Maps the ``jobs`` table per system design §2.1, using modern SQLAlchemy 2.0
``Mapped`` / ``mapped_column`` syntax.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, SmallInteger, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base, TimestampMixin


class Job(TimestampMixin, Base):
    """Represents a schedulable job."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_scheduled", "status", "scheduled_at"),
        Index("ix_jobs_priority", "priority"),
        Index("ix_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("2"),
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'pending'"),
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    error_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
    )
    retry_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    max_retries: Mapped[int] = mapped_column(
        nullable=False,
        default=3,
        server_default=text("3"),
    )
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    interval: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        default=None,
    )

    # -- Relationships -------------------------------------------------------

    execution_logs: Mapped[list[ExecutionLog]] = relationship(
        "ExecutionLog",
        back_populates="job",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Children that depend on *this* job (this job is the parent)
    child_dependencies: Mapped[list[JobDependency]] = relationship(
        "JobDependency",
        foreign_keys="JobDependency.parent_job_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # Parents that *this* job depends on (this job is the child)
    parent_dependencies: Mapped[list[JobDependency]] = relationship(
        "JobDependency",
        foreign_keys="JobDependency.child_job_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Job id={self.id!s:.8} type={self.type!r} "
            f"priority={self.priority} status={self.status!r}>"
        )


# Avoid circular import — reference via string in relationship above
from shared.models.execution_log import ExecutionLog  # noqa: E402, F811
from shared.models.job_dependency import JobDependency  # noqa: E402, F811

"""Execution log ORM model — structured event logging for job lifecycle.

Every significant job event (created, started, retried, failed, cancelled,
completed) is recorded as a row in this table with structured JSON data.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class ExecutionLog(Base):
    """Structured log entry for a job lifecycle event."""

    __tablename__ = "execution_logs"
    __table_args__ = (Index("ix_execution_logs_job_created", "job_id", "created_at"),)

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    log_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # -- Relationships -------------------------------------------------------

    job: Mapped[Job] = relationship(
        "Job",
        back_populates="execution_logs",
    )

    def __repr__(self) -> str:
        return f"<ExecutionLog id={self.id} job={self.job_id!s:.8} event={self.event_type!r}>"


from shared.models.job import Job  # noqa: E402, F811

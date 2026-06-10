"""Job dependency ORM model — DAG edge table.

Composite primary key ``(parent_job_id, child_job_id)`` represents a directed
edge: the child cannot execute until the parent has completed.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class JobDependency(Base):
    """Represents a parent → child dependency edge in a DAG workflow."""

    __tablename__ = "job_dependencies"

    parent_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    child_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        primary_key=True,
    )

    # -- Relationships (back-references to Job) ---------------------------

    parent_job: Mapped[Job] = relationship(
        "Job",
        foreign_keys=[parent_job_id],
        overlaps="child_dependencies",
    )
    child_job: Mapped[Job] = relationship(
        "Job",
        foreign_keys=[child_job_id],
        overlaps="parent_dependencies",
    )

    def __repr__(self) -> str:
        return f"<JobDependency parent={self.parent_job_id!s:.8} → child={self.child_job_id!s:.8}>"


from shared.models.job import Job  # noqa: E402, F811

"""SQLAlchemy 2.0 declarative base and shared mixins."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class TimestampMixin:
    """Mixin that adds ``created_at`` and ``updated_at`` columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # DDL default for raw SQL inserts
        default=lambda: datetime.now(UTC),  # ORM default — set in Python, never expires
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),  # DDL default
        default=lambda: datetime.now(UTC),  # ORM insert default
        onupdate=lambda: datetime.now(UTC),  # ORM update default — set in Python, never expires
        nullable=False,
    )

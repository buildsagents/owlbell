"""
Base SQLAlchemy configuration and mixins for all models.

Location: backend/db/models/base.py

Provides:
- ``Base``: SQLAlchemy 2.0 declarative base with naming conventions
- ``UUIDMixin``: UUID primary key mixin
- ``TimestampMixin``: created_at / updated_at auto-timestamps
- ``TenantMixin``: tenant_id FK for row-level multi-tenant isolation
- ``SoftDeleteMixin``: deleted_at soft-delete support
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import (
    ForeignKey,
    MetaData,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    declared_attr,
)


# Naming convention for constraints (Alembic best practice)
CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.

    Provides:
    - Metadata with constraint naming convention (Alembic-friendly)
    - Automatic table name generation from class name
    - JSONB type annotation mapping for dict/list columns
    """

    metadata = MetaData(naming_convention=CONVENTION)

    # Default column types for type annotation map
    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[str]: JSONB,
        Optional[dict[str, Any]]: JSONB,
    }

    @declared_attr.directive
    @classmethod
    def __tablename__(cls) -> str:
        """Auto-generate table name from class name."""
        return cls.__name__.lower() + "s"


class UUIDMixin:
    """Mixin that adds a UUID primary key to any model."""

    id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        comment="Primary key — UUID for distributed safety and obfuscation",
    )


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamps to any model.

    Uses ``server_default=text("now()")`` for database-level defaults.
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        nullable=False,
        comment="Record creation timestamp (UTC)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
        comment="Record last-update timestamp (UTC)",
    )


class TenantMixin:
    """Mixin that adds tenant_id to any model.

    All tenant-scoped tables inherit this for row-level tenant isolation.
    The ``tenant_id`` column references ``tenants.id`` with CASCADE delete.
    """

    tenant_id: Mapped[Any] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to tenants.id — row-level tenant isolation",
    )


class SoftDeleteMixin:
    """Mixin that adds soft-delete support via deleted_at.

    Records are never truly deleted; ``deleted_at`` is set to the current
    timestamp. Query filters should exclude rows where ``is_deleted`` is
    ``True``.
    """

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="NULL = active, timestamp = soft-deleted",
    )

    @property
    def is_deleted(self) -> bool:
        """Return ``True`` if this record has been soft-deleted."""
        return self.deleted_at is not None

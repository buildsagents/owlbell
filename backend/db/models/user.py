"""
User models — staff members who access the dashboard.

Location: backend/db/models/user.py

A ``User`` belongs to exactly one ``Tenant`` and has a role that
determines their permissions within the tenant's organization.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from backend.db.models.enums import UserRole

if TYPE_CHECKING:
    from backend.db.models.tenant import Tenant


class User(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Staff member with dashboard access.

    Email is unique **per tenant** (not globally) to allow the same
    person to be invited to multiple organizations.
    """

    __tablename__ = "users"

    # ── Identity ──────────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )
    email: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Login email"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="bcrypt hash"
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.VIEWER, nullable=False
    )
    phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Direct dial for transfers"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # ── Status ────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Preferences ───────────────────────────────────────────────

    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )
    notification_prefs: Mapped[dict] = mapped_column(
        JSONB,
        default=lambda: {
            "email_call_summary": True,
            "email_voicemail": True,
            "email_appointment": True,
            "sms_call_summary": False,
            "dashboard_sound": True,
        },
        comment="Per-user notification preferences",
    )

    # ── API Access ────────────────────────────────────────────────

    api_key_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="For service-to-service auth"
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="users"
    )

    # ── Table Args ────────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "email", name="uq_user_email_per_tenant"
        ),
    )

    @property
    def full_name(self) -> str:
        """Return the user's full name."""
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, email='{self.email}', role={self.role})>"
        )

"""
Per-tenant external integration IDs (Retell, Stripe, etc.).

Location: backend/db/models/tenant_integrations.py

Replaces scattered keys in ``tenants.config_json`` for queryable, indexed lookups.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from backend.db.models.tenant import Tenant


class TenantIntegrations(Base, TimestampMixin):
    """Canonical Retell + Stripe identifiers for a tenant (one row per tenant)."""

    __tablename__ = "tenant_integrations"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    voice_provider: Mapped[str] = mapped_column(
        String(20), default="retell", nullable=False,
        comment="retell | vapi (legacy)",
    )
    retell_agent_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, unique=True, index=True,
    )
    retell_llm_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    retell_kb_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    retell_phone_number: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, index=True,
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    stripe_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="integrations", uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<TenantIntegrations(tenant_id={self.tenant_id}, "
            f"retell_agent_id={self.retell_agent_id!r})>"
        )


class StripeWebhookEvent(Base):
    """Processed Stripe webhook events for idempotent handling."""

    __tablename__ = "stripe_webhook_events"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False,
    )
    action: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<StripeWebhookEvent(event_id={self.event_id!r})>"
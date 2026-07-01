"""
Operations models — usage metering, audit logging, plan definitions.

Location: backend/db/models/operations.py

Models for tracking billable resource consumption, maintaining an
immutable audit trail for compliance, and defining subscription plan
features and limits.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models.base import Base, TenantMixin, TimestampMixin
from backend.db.models.enums import ActorType, PlanTier


class UsageRecord(Base, TenantMixin):
    """Individual metering and billing event.

    Written in batch by the usage aggregator. One row per billable
    action (call minute, STT second, LLM token, TTS character, etc.).
    Time-bucketed columns enable fast aggregation queries.
    """

    __tablename__ = "usage_records"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Event ─────────────────────────────────────────────────────

    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="'call', 'stt', 'tts', 'llm', 'storage'",
    )
    event_subtype: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="'inbound', 'outbound', 'whisper', 'piper'",
    )

    # ── Reference ─────────────────────────────────────────────────

    call_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id"),
        nullable=True,
    )
    resource_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True), nullable=True, comment="Generic reference"
    )

    # ── Quantity ──────────────────────────────────────────────────

    quantity: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False,
        comment="Amount consumed (minutes, tokens, MB)",
    )
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="'minutes', 'tokens', 'seconds', 'mb'",
    )

    # ── Cost ──────────────────────────────────────────────────────

    cost_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 8), default=Decimal("0.0"), nullable=False
    )
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), default=Decimal("0.0"), nullable=False
    )

    # ── Time Bucketing ────────────────────────────────────────────

    period_hour: Mapped[datetime] = mapped_column(
        nullable=False, comment="Truncated to hour"
    )
    period_day: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    period_month: Mapped[str] = mapped_column(
        String(7), nullable=False, comment="YYYY-MM"
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<UsageRecord(id={self.id}, type='{self.event_type}', "
            f"qty={self.quantity} {self.unit})>"
        )


class AuditLog(Base):
    """Compliance and security audit trail.

    High-volume append-only table tracking every significant action
    in the system. Uses ``BIGSERIAL`` (``BigInteger``) for the primary
    key to handle high write throughput.

    **Never update or delete rows in this table.** It is immutable
    by design for compliance and forensic analysis.
    """

    __tablename__ = "audit_logs"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )

    # ── Tenant (not FK for performance) ───────────────────────────

    tenant_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, index=True,
    )

    # ── Actor ─────────────────────────────────────────────────────

    actor_type: Mapped[ActorType] = mapped_column(nullable=False)
    actor_id: Mapped[Optional[PgUUID]] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # ── Action ────────────────────────────────────────────────────

    action: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. 'call.answer', 'user.login', 'setting.update'",
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="e.g. 'call', 'user'",
    )
    resource_id: Mapped[Optional[PgUUID]] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    # ── Details ───────────────────────────────────────────────────

    details_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Before/after values",
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # ── Severity ──────────────────────────────────────────────────

    severity: Mapped[str] = mapped_column(
        String(10), default="info", nullable=False,
        comment="debug | info | warning | error | critical",
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, action='{self.action}', "
            f"severity='{self.severity}')>"
        )


class PlanDefinition(Base, TimestampMixin):
    """Subscription plan feature definitions.

    Defines the limits, features, and pricing for each plan tier.
    Loaded at startup and cached in Redis. Editable by super-admin
    only. Plan definitions are global (no tenant_id).
    """

    __tablename__ = "plan_definitions"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Identity ──────────────────────────────────────────────────

    plan_tier: Mapped[PlanTier] = mapped_column(
        nullable=False, unique=True
    )
    display_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── Limits ────────────────────────────────────────────────────

    max_minutes_monthly: Mapped[int] = mapped_column(
        default=100, nullable=False
    )
    max_concurrent_calls: Mapped[int] = mapped_column(
        default=1, nullable=False
    )
    max_users: Mapped[int] = mapped_column(
        default=1, nullable=False
    )
    max_phone_numbers: Mapped[int] = mapped_column(
        default=1, nullable=False
    )

    # ── Features ──────────────────────────────────────────────────

    features_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Feature flags map: {feature_name: true/false}",
    )

    # ── Display ───────────────────────────────────────────────────

    is_public: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Shown on pricing page"
    )
    sort_order: Mapped[int] = mapped_column(
        default=0, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<PlanDefinition(tier={self.plan_tier}, "
            f"name='{self.display_name}')>"
        )

"""
Business logic models — appointments, routing, FAQ, hours, caller profiles.

Location: backend/db/models/business.py

Models that encode business-specific logic: appointment booking,
call routing rules, FAQ knowledge base, operating hours, caller
CRM profiles, call summaries, and notification logs.
"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from backend.db.models.enums import (
    AppointmentStatus,
    IntegrationProvider,
    NotificationChannel,
    QuoteStatus,
    RoutingAction,
    RoutingType,
)

if TYPE_CHECKING:
    from backend.db.models.call import Call
    from backend.db.models.tenant import Tenant
    from backend.db.models.user import User


class Appointment(Base, TenantMixin, TimestampMixin):
    """Appointment bookings handled by the AI.

    Created when a caller requests scheduling. May be linked to a
    specific call and can sync to external calendar providers.
    """

    __tablename__ = "appointments"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    call_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id"),
        nullable=True,
        comment="May be booked via call",
    )

    # ── Caller Info ───────────────────────────────────────────────

    caller_number: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    caller_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # ── Appointment Details ───────────────────────────────────────

    title: Mapped[str] = mapped_column(
        String(255), default="Appointment", nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        default=AppointmentStatus.PENDING, nullable=False
    )

    # ── Timing ────────────────────────────────────────────────────

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )

    # ── Location / Type ───────────────────────────────────────────

    appointment_type: Mapped[str] = mapped_column(
        String(50), default="in_person", nullable=False,
        comment="in_person | phone | video | virtual",
    )
    location: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # ── Attendee ──────────────────────────────────────────────────

    staff_user_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="Assigned staff",
    )
    staff_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Denormalized for display"
    )

    # ── Confirmation ──────────────────────────────────────────────

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    confirmed_by: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="ai | staff | caller | system",
    )
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Completion / Reviews ──────────────────────────────────────

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="Set when status transitions to completed"
    )
    review_requested_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True, comment="Set when a post-job review text was sent"
    )

    # ── Cancellation ──────────────────────────────────────────────

    cancelled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── Calendar Sync ─────────────────────────────────────────────

    external_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Google/Outlook event ID"
    )
    external_provider: Mapped[Optional[IntegrationProvider]] = mapped_column(
        nullable=True
    )
    sync_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | synced | failed | conflict",
    )
    sync_error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── Metadata ──────────────────────────────────────────────────

    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="appointments"
    )

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        CheckConstraint(
            "end_time > start_time",
            name="time_order",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Appointment(id={self.id}, date={self.scheduled_date}, "
            f"status={self.status})>"
        )


class Quote(Base, TenantMixin, TimestampMixin):
    """A customer quote / estimate the AI can chase until it's resolved.

    Typically created by the business owner (or their field-service tool via
    the API) after pricing a job. While a quote sits in ``SENT``, the
    quote-follow-up automation texts the customer on a cadence until it is
    accepted, declined, or expires.
    """

    __tablename__ = "quotes"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    call_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id"),
        nullable=True,
        comment="Originating call, if any",
    )

    # ── Customer ──────────────────────────────────────────────────

    customer_number: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Quote Details ─────────────────────────────────────────────

    title: Mapped[str] = mapped_column(String(255), default="Quote", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="GBP", nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(
        default=QuoteStatus.SENT, nullable=False
    )

    # ── Lifecycle ─────────────────────────────────────────────────

    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    declined_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Follow-up tracking ────────────────────────────────────────

    last_followup_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    followup_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Metadata ──────────────────────────────────────────────────

    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship("Tenant")

    def __repr__(self) -> str:
        return f"<Quote(id={self.id}, status={self.status}, amount={self.amount})>"


class RoutingRule(Base, TenantMixin, TimestampMixin):
    """Call routing configuration per tenant.

    Rules are evaluated in priority order (lower number = higher
    priority). The first matching rule determines the action taken
    when a call arrives.
    """

    __tablename__ = "routing_rules"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Rule Identity ─────────────────────────────────────────────

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(
        default=100, nullable=False, comment="Lower = higher priority"
    )

    # ── Matching Conditions ───────────────────────────────────────

    rule_type: Mapped[RoutingType] = mapped_column(nullable=False)
    conditions_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="JSON conditions for rule matching",
    )

    # ── Action ────────────────────────────────────────────────────

    action: Mapped[RoutingAction] = mapped_column(nullable=False)
    action_config_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="JSON parameters for the action",
    )

    # ── Status ────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Stats ─────────────────────────────────────────────────────

    match_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Times this rule matched"
    )

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "priority", name="uq_rule_priority"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RoutingRule(id={self.id}, name='{self.name}', "
            f"priority={self.priority})>"
        )


class FAQEntry(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """FAQ knowledge base entry per tenant.

    Used by the AI to answer common caller questions. Supports
    multiple question variants for better matching and tracks
    usage statistics to identify the most valuable entries.
    """

    __tablename__ = "faq_entries"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Content ───────────────────────────────────────────────────

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(100), default="general", nullable=False
    )
    tags_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )

    # ── Variants ──────────────────────────────────────────────────

    question_variants_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]",
        comment='["alternate phrasing 1", ...]',
    )

    # ── AI Enhancement ────────────────────────────────────────────

    embeddings_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Vector embeddings (future)"
    )

    # ── Full-Text Search ──────────────────────────────────────────

    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, nullable=True, comment="Updated via trigger"
    )

    # ── Usage Stats ───────────────────────────────────────────────

    use_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Times used by AI"
    )
    helpful_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Caller marked helpful"
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Status ────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="faq_entries"
    )

    def __repr__(self) -> str:
        q = self.question[:50] if self.question else ""
        return f"<FAQEntry(id={self.id}, q='{q}...')>"


class BusinessHours(Base, TenantMixin, TimestampMixin):
    """Operating hours per tenant.

    Defines regular weekly hours plus optional overrides for
    special dates (holidays, early closure, etc.).
    """

    __tablename__ = "business_hours"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Day & Hours ───────────────────────────────────────────────

    day_of_week: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="monday | tuesday | ... | sunday",
    )
    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_closed: Mapped[bool] = mapped_column(
        default=False, nullable=False, comment="Closed all day"
    )

    # ── Override ──────────────────────────────────────────────────

    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )
    effective_from: Mapped[date] = mapped_column(
        Date, nullable=False, default=date.today
    )
    effective_to: Mapped[Optional[date]] = mapped_column(
        nullable=True, comment="NULL = ongoing"
    )

    is_override: Mapped[bool] = mapped_column(
        default=False, nullable=False,
        comment="True for holiday/special hours",
    )
    override_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="e.g. 'Christmas Day'"
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="business_hours"
    )

    def __repr__(self) -> str:
        return (
            f"<BusinessHours(day={self.day_of_week}, "
            f"{self.open_time}-{self.close_time})>"
        )


class HolidaySchedule(Base, TenantMixin, TimestampMixin):
    """Holiday schedule overrides per tenant.

    Dedicated table for holiday closures and modified hours.
    Simplifies calendar integration and annual recurrence.
    """

    __tablename__ = "holiday_schedules"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Holiday Info ──────────────────────────────────────────────

    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="e.g. 'Christmas Day'"
    )
    is_closed: Mapped[bool] = mapped_column(
        default=True, nullable=False, comment="Closed all day"
    )

    # ── Modified Hours (when not fully closed) ────────────────────

    open_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True, comment="NULL if closed all day"
    )
    close_time: Mapped[Optional[time]] = mapped_column(
        Time, nullable=True, comment="NULL if closed all day"
    )
    timezone: Mapped[str] = mapped_column(
        String(50), default="America/New_York", nullable=False
    )

    # ── Recurrence ────────────────────────────────────────────────

    is_recurring: Mapped[bool] = mapped_column(
        default=True, nullable=False,
        comment="Repeats annually on same month/day",
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship("Tenant")

    def __repr__(self) -> str:
        status = "closed" if self.is_closed else f"{self.open_time}-{self.close_time}"
        return f"<HolidaySchedule(date={self.date}, name='{self.name}', {status})>"


class CallerProfile(Base, TenantMixin, TimestampMixin):
    """Known caller profile (CRM-lite).

    Builds a profile for repeat callers including contact info,
    AI-generated summaries, tags, priority level, and interaction
    statistics.
    """

    __tablename__ = "caller_profiles"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Identity ──────────────────────────────────────────────────

    phone_number: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="E.164"
    )
    phone_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="SHA-256 normalized number"
    )

    # ── Profile ───────────────────────────────────────────────────

    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    company: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )

    # ── AI-Generated ──────────────────────────────────────────────

    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="LLM summary of interactions"
    )
    preferred_language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False
    )

    # ── Stats ─────────────────────────────────────────────────────

    total_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    total_duration_sec: Mapped[int] = mapped_column(
        default=0, nullable=False
    )
    last_call_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── VIP / Blocklist ───────────────────────────────────────────

    priority: Mapped[str] = mapped_column(
        String(20), default="normal", nullable=False,
        comment="blocked | low | normal | high | vip",
    )

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "phone_hash", name="uq_caller_per_tenant"
        ),
        CheckConstraint(
            "priority IN ('blocked', 'low', 'normal', 'high', 'vip')",
            name="priority_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CallerProfile(id={self.id}, phone='{self.phone_number}', "
            f"name='{self.name}')>"
        )


class CallSummary(Base, TenantMixin, TimestampMixin):
    """AI-generated summary of a completed call.

    Post-call analysis including natural language summary, sentiment,
    extracted key points, and action items for follow-up.
    """

    __tablename__ = "call_summaries"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Foreign Key ───────────────────────────────────────────────

    call_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ── Summary Content ───────────────────────────────────────────

    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Natural language summary"
    )
    sentiment: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True,
        comment="positive | neutral | negative",
    )
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="-1.0 to +1.0"
    )
    key_points_json: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, comment="Extracted key discussion points"
    )
    action_items_json: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True, comment="Follow-up action items"
    )

    # ── Caller Intent ─────────────────────────────────────────────

    primary_intent: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    intents_detected_json: Mapped[Optional[list]] = mapped_column(
        JSONB, nullable=True
    )

    # ── Quality ───────────────────────────────────────────────────

    call_quality_score: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="1-10 subjective quality"
    )

    def __repr__(self) -> str:
        return (
            f"<CallSummary(call_id={self.call_id}, "
            f"sentiment={self.sentiment})>"
        )


class NotificationLog(Base, TenantMixin, TimestampMixin):
    """Log of notifications sent to tenant staff or external systems.

    Tracks delivery status for all notification channels: email, SMS,
    Slack, webhook, and in-app alerts.
    """

    __tablename__ = "notification_logs"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Notification Details ──────────────────────────────────────

    channel: Mapped[NotificationChannel] = mapped_column(nullable=False)
    recipient: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Email, phone, URL, or channel ID",
    )
    subject: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_html: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── Context ───────────────────────────────────────────────────

    event_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True,
        comment="call.completed | voicemail.received | etc.",
    )
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="call | appointment | etc."
    )
    entity_id: Mapped[Optional[PgUUID]] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    # ── Status ────────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | sent | delivered | failed | bounced",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Provider Metadata ─────────────────────────────────────────

    provider_message_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="External message ID"
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationLog(id={self.id}, channel={self.channel}, "
            f"status='{self.status}')>"
        )

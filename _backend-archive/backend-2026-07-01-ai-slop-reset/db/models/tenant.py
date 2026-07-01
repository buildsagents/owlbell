"""
Tenant models — root of multi-tenancy.

Location: backend/db/models/tenant.py

Every business using Owlbell is a **tenant**. All other tables
reference this via ``tenant_id`` for row-level data isolation.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, TimestampMixin
from backend.db.models.enums import AIModel, PlanTier, TenantStatus, TranscriptSource, VoiceType

if TYPE_CHECKING:
    from backend.db.models.user import User
    from backend.db.models.call import Call
    from backend.db.models.business import FAQEntry, Appointment, BusinessHours
    from backend.db.models.tenant_integrations import TenantIntegrations


class Tenant(Base, TimestampMixin):
    """Root multi-tenant entity. Every business is a tenant.

    Contains the full business profile, AI configuration, call-handling
    settings, and relationships to all tenant-scoped entities.
    """

    __tablename__ = "tenants"

    # ── Identity ──────────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slug: Mapped[str] = mapped_column(
        String(63),
        unique=True,
        nullable=False,
        comment="URL-safe identifier: acme-corp",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Business display name"
    )
    status: Mapped[TenantStatus] = mapped_column(
        default=TenantStatus.ACTIVE, nullable=False
    )
    plan_tier: Mapped[PlanTier] = mapped_column(
        default=PlanTier.FREE, nullable=False
    )
    plan_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Business Profile ──────────────────────────────────────────

    business_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    business_phone: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="E.164 format"
    )
    business_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    business_timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="America/New_York",
    )
    business_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    business_website: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    industry: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="e.g. 'healthcare', 'legal', 'retail'"
    )

    # ── AI Configuration ──────────────────────────────────────────

    ai_model: Mapped[AIModel] = mapped_column(
        default=AIModel.LLAMA3_8B, nullable=False
    )
    ai_temperature: Mapped[float] = mapped_column(
        default=0.7,
        nullable=False,
        comment="LLM temperature 0.0-2.0",
    )
    ai_max_tokens: Mapped[int] = mapped_column(
        default=256, nullable=False
    )
    ai_system_prompt: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Override default system prompt"
    )
    voice_type: Mapped[VoiceType] = mapped_column(
        default=VoiceType.PIPER_DEFAULT, nullable=False
    )
    voice_speed: Mapped[float] = mapped_column(
        default=1.0, nullable=False
    )
    stt_model: Mapped[TranscriptSource] = mapped_column(
        default=TranscriptSource.WHISPER_LOCAL, nullable=False
    )
    stt_language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False
    )

    # ── Call Handling ─────────────────────────────────────────────

    max_call_duration: Mapped[int] = mapped_column(
        default=600, nullable=False, comment="seconds (10 min)"
    )
    voicemail_enabled: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    voicemail_greeting: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    after_hours_action: Mapped[str] = mapped_column(
        String(20), default="voicemail", nullable=False
    )
    concurrent_calls_max: Mapped[int] = mapped_column(
        default=5, nullable=False
    )

    # ── Customization ─────────────────────────────────────────────

    greeting_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="First thing AI says"
    )
    hold_music_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )
    transfer_number: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Fallback transfer number"
    )

    # ── Metadata ──────────────────────────────────────────────────

    config_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    features_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Tenant Admin / Onboarding ─────────────────────────────────

    subdomain: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True,
        comment="Unique subdomain for tenant portal"
    )
    owner_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Tenant owner email"
    )
    locale: Mapped[str] = mapped_column(
        String(10), default="en-US", nullable=False
    )
    current_period: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True, comment="Current billing period YYYY-MM"
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Usage and billing metadata"
    )

    # ── Soft Delete ───────────────────────────────────────────────

    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────────

    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="tenant",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    calls: Mapped[list["Call"]] = relationship(
        "Call",
        back_populates="tenant",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    faq_entries: Mapped[list["FAQEntry"]] = relationship(
        "FAQEntry",
        back_populates="tenant",
        lazy="selectin",
    )
    appointments: Mapped[list["Appointment"]] = relationship(
        "Appointment",
        back_populates="tenant",
        lazy="selectin",
    )
    business_hours: Mapped[list["BusinessHours"]] = relationship(
        "BusinessHours",
        back_populates="tenant",
        lazy="selectin",
    )
    config: Mapped[Optional["TenantConfig"]] = relationship(
        "TenantConfig",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    integrations: Mapped[Optional["TenantIntegrations"]] = relationship(
        "TenantIntegrations",
        back_populates="tenant",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # ── Table Args ────────────────────────────────────────────────

    __table_args__ = (
        CheckConstraint(
            "slug ~ '^[a-z0-9-]+$'",
            name="slug_format",
        ),
        CheckConstraint(
            "ai_temperature BETWEEN 0.0 AND 2.0",
            name="temperature_range",
        ),
        CheckConstraint(
            "voice_speed BETWEEN 0.5 AND 2.0",
            name="voice_speed_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"
        )


class TenantConfig(Base, TimestampMixin):
    """Per-tenant configuration settings.

    Split from ``Tenant`` for cleaner updates. All settings use JSONB
    columns for extensibility without schema migrations.
    """

    __tablename__ = "tenant_configs"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    tenant_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # AI behavior settings (JSONB for extensibility)
    ai_settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        comment="AI behavior: voice_id, speech_rate, greeting, language, etc.",
    )

    # Call routing configuration
    routing_rules: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        comment="Call routing: business_hours, after_hours_action, overflow",
    )

    # Notification preferences
    notification_settings: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        comment="Notification: email, sms, daily_summary, missed_call_alert",
    )

    # Integration settings
    integrations: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        comment="Third-party integrations: calendar, CRM, etc.",
    )

    # Relationship
    tenant: Mapped["Tenant"] = relationship(
        "Tenant",
        back_populates="config",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<TenantConfig(tenant_id={self.tenant_id})>"

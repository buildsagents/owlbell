"""
Call, CallLeg, and Recording models.

Location: backend/db/models/call.py

Models for tracking phone calls, their participants (legs), and
audio recordings. The ``Call`` table is the primary call session
record and may be partitioned by month on ``partition_key``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, TenantMixin, TimestampMixin
from backend.db.models.enums import AIModel, CallDirection, CallResult, CallStatus

if TYPE_CHECKING:
    from backend.db.models.tenant import Tenant
    from backend.db.models.ai import Transcript, Conversation, ToolCall


class Call(Base, TenantMixin, TimestampMixin):
    """Primary call session record.

    Tracks the full lifecycle of a phone call from ``queued`` through
    ``completed`` or ``failed``. Stores AI interaction metadata,
    quality metrics, billing estimates, and relationships to legs,
    transcripts, recordings, and conversation.
    """

    __tablename__ = "calls"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Call Identification ───────────────────────────────────────

    call_sid: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, comment="FreeSWITCH call UUID"
    )
    parent_call_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id"),
        nullable=True,
        comment="For transferred calls",
    )

    # ── Direction & Routing ───────────────────────────────────────

    direction: Mapped[CallDirection] = mapped_column(nullable=False)
    caller_number: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="E.164"
    )
    caller_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="CNAM if available"
    )
    caller_id_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="SHA-256 for dedup"
    )
    destination_number: Mapped[str] = mapped_column(
        String(30), nullable=False, comment="Called number (DID)"
    )

    # ── Status & Result ───────────────────────────────────────────

    status: Mapped[CallStatus] = mapped_column(
        default=CallStatus.QUEUED, nullable=False
    )
    result: Mapped[Optional[CallResult]] = mapped_column(nullable=True)

    # ── Timing ────────────────────────────────────────────────────

    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Total call duration in seconds"
    )
    talk_time_seconds: Mapped[int] = mapped_column(
        default=0, comment="Time after answer"
    )

    # ── AI Interaction Summary ────────────────────────────────────

    ai_handled: Mapped[bool] = mapped_column(
        default=False, nullable=False, comment="Was AI involved?"
    )
    ai_model_used: Mapped[Optional[AIModel]] = mapped_column(nullable=True)
    transcript_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="LLM-generated summary"
    )
    sentiment_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="-1.0 to +1.0"
    )
    intent_detected: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Primary intent"
    )

    # ── Transfer Info ─────────────────────────────────────────────

    transferred_to: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, comment="Number transferred to"
    )
    transfer_reason: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # ── Quality Metrics ───────────────────────────────────────────

    audio_quality_mos: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True, comment="Mean Opinion Score"
    )
    stt_confidence_avg: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="Average STT confidence"
    )
    llm_tokens_used: Mapped[int] = mapped_column(default=0)
    tts_chars_used: Mapped[int] = mapped_column(default=0)

    # ── Voicemail ─────────────────────────────────────────────────

    voicemail_left: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    voicemail_duration: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="seconds"
    )

    # ── Cost & Billing ────────────────────────────────────────────

    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), default=Decimal("0.0"), nullable=False
    )

    # ── Metadata ──────────────────────────────────────────────────

    tags: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Partitioning ──────────────────────────────────────────────

    partition_key: Mapped[Optional[str]] = mapped_column(
        String(7), nullable=True, comment="YYYY-MM for partition pruning"
    )

    # ── Relationships ─────────────────────────────────────────────

    tenant: Mapped["Tenant"] = relationship(
        "Tenant", back_populates="calls"
    )
    legs: Mapped[list["CallLeg"]] = relationship(
        "CallLeg",
        back_populates="call",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript",
        back_populates="call",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    recordings: Mapped[list["Recording"]] = relationship(
        "Recording",
        back_populates="call",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation",
        back_populates="call",
        lazy="selectin",
        uselist=False,
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall",
        back_populates="call",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return (
            f"<Call(id={self.id}, sid='{self.call_sid}', "
            f"status={self.status})>"
        )


class CallLeg(Base, TenantMixin, TimestampMixin):
    """Individual party in a call (caller, AI, transferred human).

    Tracks each participant's media details, join/leave timing, and status.
    A call has at least one leg (the caller) and may accumulate additional
    legs through transfers or conferences.
    """

    __tablename__ = "call_legs"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    call_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Leg Identity ──────────────────────────────────────────────

    leg_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="caller | ai_agent | human_agent | voicemail | conference",
    )
    leg_index: Mapped[int] = mapped_column(
        default=1, nullable=False, comment="Order of legs"
    )
    display_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="e.g. 'AI Agent', 'John Smith'"
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )
    user_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
        comment="If staff member",
    )

    # ── Media ─────────────────────────────────────────────────────

    sip_call_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True
    )
    local_sdp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remote_sdp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rtp_local_ip: Mapped[Optional[str]] = mapped_column(nullable=True)
    rtp_local_port: Mapped[Optional[int]] = mapped_column(nullable=True)

    # ── Timing ────────────────────────────────────────────────────

    joined_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    left_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False,
        comment="active | hold | muted | disconnected",
    )

    # ── Relationships ─────────────────────────────────────────────

    call: Mapped["Call"] = relationship("Call", back_populates="legs")

    def __repr__(self) -> str:
        return (
            f"<CallLeg(id={self.id}, type='{self.leg_type}', "
            f"call={self.call_id})>"
        )


class Recording(Base, TenantMixin, TimestampMixin):
    """Audio recording of a call or call leg.

    Stores file metadata, storage backend details, and access control.
    Actual audio files may be stored locally or on S3/MinIO.
    """

    __tablename__ = "recordings"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    call_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_leg_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("call_legs.id"),
        nullable=True,
    )

    # ── File Info ─────────────────────────────────────────────────

    file_path: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Relative path on storage"
    )
    file_size_bytes: Mapped[int] = mapped_column(nullable=False)
    file_format: Mapped[str] = mapped_column(
        String(10), default="wav", nullable=False,
        comment="wav | mp3 | ogg | webm",
    )
    duration_seconds: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False
    )
    sample_rate: Mapped[int] = mapped_column(
        default=16000, nullable=False
    )
    channels: Mapped[int] = mapped_column(default=1, nullable=False)

    # ── Storage ───────────────────────────────────────────────────

    storage_backend: Mapped[str] = mapped_column(
        String(20), default="local", nullable=False,
        comment="local | s3 | minio",
    )
    storage_bucket: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )
    storage_key: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )

    # ── Access Control ────────────────────────────────────────────

    is_deleted: Mapped[bool] = mapped_column(
        default=False, nullable=False, comment="Soft delete"
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    delete_after_days: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Auto-delete policy"
    )

    # ── Public Access ─────────────────────────────────────────────

    access_url: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True, comment="Temporary signed URL"
    )
    access_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Relationships ─────────────────────────────────────────────

    call: Mapped["Call"] = relationship("Call", back_populates="recordings")

    def __repr__(self) -> str:
        return (
            f"<Recording(id={self.id}, call={self.call_id}, "
            f"duration={self.duration_seconds}s)>"
        )

"""
AI pipeline models — Transcript, Conversation, Message, Prompt, and ToolCall.

Location: backend/db/models/ai.py

Models for speech-to-text output, AI conversation threads, individual
messages, versioned system prompts, and AI tool/function invocations.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, TenantMixin, TimestampMixin
from backend.db.models.enums import (
    AIModel as AIModelEnum,
    MessageRole,
    MessageType,
    TranscriptSource,
)

if TYPE_CHECKING:
    from backend.db.models.call import Call


class Transcript(Base, TenantMixin):
    """Speech-to-text output segment.

    Each row represents a single contiguous utterance from one speaker
    within a call. Per-word timestamps and confidence are stored in
    ``words_json`` for advanced analytics.
    """

    __tablename__ = "transcripts"

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

    # ── Source ────────────────────────────────────────────────────

    source: Mapped[TranscriptSource] = mapped_column(
        default=TranscriptSource.WHISPER_LOCAL, nullable=False
    )
    model_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="e.g. 'whisper.cpp:v1.5.4'"
    )
    language: Mapped[str] = mapped_column(
        String(10), default="en", nullable=False
    )

    # ── Timing ────────────────────────────────────────────────────

    segment_start: Mapped[Decimal] = mapped_column(
        Numeric(8, 3), nullable=False, comment="seconds from call start"
    )
    segment_end: Mapped[Decimal] = mapped_column(
        Numeric(8, 3), nullable=False
    )

    # ── Content ───────────────────────────────────────────────────

    speaker: Mapped[str] = mapped_column(
        String(20), default="unknown", nullable=False,
        comment="caller | agent | unknown",
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_normalized: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Lowercase, normalized"
    )

    # ── Confidence ────────────────────────────────────────────────

    confidence: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="0.000 to 1.000"
    )
    words_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Per-word timestamps & confidence"
    )

    # ── Full-Text Search ──────────────────────────────────────────

    search_vector: Mapped[Optional[str]] = mapped_column(
        TSVECTOR, nullable=True, comment="Updated via trigger"
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    # ── Relationships ─────────────────────────────────────────────

    call: Mapped["Call"] = relationship("Call", back_populates="transcripts")

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        CheckConstraint(
            "segment_end > segment_start",
            name="segment_timing",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Transcript(id={self.id}, start={self.segment_start}s, "
            f"speaker='{self.speaker}')>"
        )


class Conversation(Base, TenantMixin, TimestampMixin):
    """AI conversation thread within a call.

    Each call has exactly one conversation. This model tracks the
    high-level outcome: topic, summary, resolution status, and
    estimated caller satisfaction.
    """

    __tablename__ = "conversations"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    call_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ── Conversation Metadata ─────────────────────────────────────

    turn_count: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Number of exchanges"
    )
    topic_category: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Classified topic"
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="LLM-generated summary"
    )
    satisfaction_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="Estimated caller satisfaction"
    )

    # ── Resolution ────────────────────────────────────────────────

    resolved: Mapped[Optional[bool]] = mapped_column(
        nullable=True, comment="Was the issue resolved?"
    )
    resolution_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="'answer_provided', 'appointment_booked', 'transferred', etc.",
    )
    follow_up_required: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────

    call: Mapped["Call"] = relationship(
        "Call", back_populates="conversation"
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        lazy="selectin",
        order_by="Message.sequence_number",
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(id={self.id}, call={self.call_id}, "
            f"turns={self.turn_count})>"
        )


class Message(Base, TenantMixin):
    """Individual message in an AI conversation.

    Represents one turn in the LLM dialog — system prompt, user
    (caller) utterance, assistant response, or tool result. Token
    counts and latency are tracked for cost analysis.
    """

    __tablename__ = "messages"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Foreign Keys ──────────────────────────────────────────────

    conversation_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    call_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Content ───────────────────────────────────────────────────

    role: Mapped[MessageRole] = mapped_column(nullable=False)
    message_type: Mapped[MessageType] = mapped_column(
        default=MessageType.TEXT, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Structured data for tool calls"
    )

    # ── LLM Metadata ──────────────────────────────────────────────

    llm_model: Mapped[Optional[AIModelEnum]] = mapped_column(nullable=True)
    llm_temperature: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(3, 2), nullable=True
    )
    tokens_prompt: Mapped[int] = mapped_column(default=0)
    tokens_completion: Mapped[int] = mapped_column(default=0)
    tokens_total: Mapped[Optional[int]] = mapped_column(nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Generation latency"
    )

    # ── Sequence ──────────────────────────────────────────────────

    sequence_number: Mapped[int] = mapped_column(
        nullable=False, comment="Order in conversation"
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow
    )

    # ── Relationships ─────────────────────────────────────────────

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    def __repr__(self) -> str:
        return (
            f"<Message(id={self.id}, role={self.role}, "
            f"seq={self.sequence_number})>"
        )


class Prompt(Base, TenantMixin, TimestampMixin):
    """System prompts and prompt templates per tenant.

    Prompts are versioned — each update creates a new version with
    ``is_active`` controlling which one is used by the AI pipeline.
    Only one prompt per ``prompt_type`` should be active at a time.
    """

    __tablename__ = "prompts"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=PgUUID
    )

    # ── Identity ──────────────────────────────────────────────────

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="system | greeting | transfer | voicemail | closing | tool_call | custom",
    )

    # ── Content ───────────────────────────────────────────────────

    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]",
        comment='Variable names e.g. ["business_name", "hours"]',
    )

    # ── Versioning ────────────────────────────────────────────────

    version: Mapped[int] = mapped_column(default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False,
        comment="Only one active per type per tenant",
    )

    # ── Usage ─────────────────────────────────────────────────────

    use_count: Mapped[int] = mapped_column(default=0, nullable=False)
    avg_response_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True, comment="User rating (future)"
    )

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        CheckConstraint(
            "prompt_type IN ('system', 'greeting', 'transfer', "
            "'voicemail', 'closing', 'tool_call', 'custom')",
            name="prompt_type_valid",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Prompt(id={self.id}, type='{self.prompt_type}', "
            f"name='{self.name}', v={self.version})>"
        )


class ToolCall(Base, TenantMixin):
    """Record of AI tool/function invocations.

    When the LLM decides to call a tool (e.g. ``book_appointment``,
    ``lookup_caller``, ``transfer_call``), this model captures the
    tool name, arguments, execution result, timing, and status.
    """

    __tablename__ = "tool_calls"

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
    message_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("messages.id"),
        nullable=True,
        comment="The message that triggered it",
    )

    # ── Tool Info ─────────────────────────────────────────────────

    tool_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="e.g. 'book_appointment'"
    )
    tool_version: Mapped[str] = mapped_column(
        String(20), default="1.0", nullable=False
    )

    # ── Input / Output ────────────────────────────────────────────

    arguments_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, comment="Parameters passed"
    )
    result_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="Result returned"
    )
    error_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True, comment="If failed"
    )

    # ── Execution ─────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | running | success | failed | timeout",
    )
    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Execution time"
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────

    call: Mapped["Call"] = relationship("Call", back_populates="tool_calls")

    def __repr__(self) -> str:
        return (
            f"<ToolCall(id={self.id}, tool='{self.tool_name}', "
            f"status='{self.status}')>"
        )

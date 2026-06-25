"""
Prompt-management models — versioned prompts and A/B tests.

Location: backend/db/models/prompts.py

Backs ``operations.prompts.manager.PromptManager``. Each prompt edit creates
a new immutable ``PromptVersionRecord``; only one version per tenant+type is
active at a time. ``PromptABTestRecord`` configures a split test between two
versions and accumulates per-variant call results.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models.base import Base, TenantMixin


class PromptVersionRecord(Base, TenantMixin):
    """A single immutable version of a tenant prompt.

    Version numbers auto-increment per ``tenant_id`` + ``prompt_type``. The
    active version is the one served by the AI pipeline; activating a new
    version archives the previously active one.
    """

    __tablename__ = "prompt_versions"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True
    )

    prompt_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="system | greeting | hold | voicemail | transfer | goodbye | fallback | custom_*",
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # ── Lifecycle ─────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False,
        comment="draft | active | archived | ab_test",
    )
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ── A/B test linkage ──────────────────────────────────────────
    ab_test_group: Mapped[Optional[str]] = mapped_column(
        String(1), nullable=True, comment="'A' or 'B' when in a test"
    )
    ab_test_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )

    # ── Performance ───────────────────────────────────────────────
    times_used: Mapped[int] = mapped_column(default=0, nullable=False)
    avg_call_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True
    )

    # ── Provenance ────────────────────────────────────────────────
    created_by: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PromptVersionRecord(id={self.id}, type='{self.prompt_type}', "
            f"v={self.version_number}, active={self.is_active})>"
        )


class PromptABTestRecord(Base, TenantMixin):
    """A/B test between two prompt versions for one prompt type."""

    __tablename__ = "prompt_ab_tests"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_type: Mapped[str] = mapped_column(String(30), nullable=False)

    variant_a_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    variant_b_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False
    )
    split_percentage: Mapped[int] = mapped_column(
        Integer, default=50, nullable=False,
        comment="Percent of traffic routed to variant B",
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    winning_variant: Mapped[Optional[str]] = mapped_column(
        String(1), nullable=True
    )

    # ── Accumulated results ───────────────────────────────────────
    total_participants: Mapped[int] = mapped_column(default=0, nullable=False)
    variant_a_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    variant_b_calls: Mapped[int] = mapped_column(default=0, nullable=False)
    variant_a_avg_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    variant_b_avg_rating: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 3), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<PromptABTestRecord(id={self.id}, name='{self.name}', "
            f"active={self.is_active})>"
        )

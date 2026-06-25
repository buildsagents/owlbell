"""
Onboarding models — client onboarding pipeline, steps, and email sequence.

Location: backend/db/models/onboarding.py

Backs ``operations.onboarding.automation`` and
``operations.onboarding.email_sequence``. One ``OnboardingPipelineRecord`` per
client tenant, with an ordered set of ``OnboardingStepRecord`` rows and the
``OnboardingEmailRecord`` rows for the post-sale email sequence.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.models.base import Base, TenantMixin


class OnboardingPipelineRecord(Base, TenantMixin):
    """Onboarding progress for a single client tenant."""

    __tablename__ = "onboarding_pipelines"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True
    )

    tenant_name: Mapped[str] = mapped_column(String(150), nullable=False)
    tenant_email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    steps: Mapped[list["OnboardingStepRecord"]] = relationship(
        "OnboardingStepRecord",
        back_populates="pipeline",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OnboardingStepRecord.step_order",
    )

    def __repr__(self) -> str:
        return (
            f"<OnboardingPipelineRecord(id={self.id}, "
            f"tenant='{self.tenant_name}')>"
        )


class OnboardingStepRecord(Base, TenantMixin):
    """A single step within an onboarding pipeline."""

    __tablename__ = "onboarding_steps"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True
    )
    pipeline_id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("onboarding_pipelines.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    step_id: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)

    auto_completes: Mapped[bool] = mapped_column(default=False, nullable=False)
    requires_action: Mapped[bool] = mapped_column(default=False, nullable=False)
    estimated_days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | in_progress | completed | blocked | skipped",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    pipeline: Mapped["OnboardingPipelineRecord"] = relationship(
        "OnboardingPipelineRecord", back_populates="steps"
    )

    def __repr__(self) -> str:
        return (
            f"<OnboardingStepRecord(step_id='{self.step_id}', "
            f"status='{self.status}')>"
        )


class OnboardingEmailRecord(Base, TenantMixin):
    """A single email in a tenant's onboarding email sequence."""

    __tablename__ = "onboarding_emails"

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True
    )
    pipeline_id: Mapped[Optional[PgUUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("onboarding_pipelines.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    email_id: Mapped[str] = mapped_column(String(120), nullable=False)
    trigger_step: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    template: Mapped[str] = mapped_column(String(80), nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | sent | delivered | opened | failed | skipped",
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    opened_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<OnboardingEmailRecord(email_id='{self.email_id}', "
            f"status='{self.status}')>"
        )

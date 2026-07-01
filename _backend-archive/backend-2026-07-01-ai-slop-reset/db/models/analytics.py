"""Pre-aggregated analytics rollups for dashboard queries."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Date, Float, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models.base import Base, TenantMixin


class AnalyticsDailyRollup(Base, TenantMixin):
    """Per-tenant daily call metrics (filled by nightly Celery job)."""

    __tablename__ = "analytics_daily_rollups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "rollup_date", name="uq_analytics_daily_tenant_date"),
    )

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    rollup_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    total_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    answered_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missed_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_handled_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_wait_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    wait_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rolled_up_at: Mapped[datetime] = mapped_column(nullable=False)
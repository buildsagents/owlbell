"""Analytics domain — rollups and metric computation."""

from __future__ import annotations

from backend.domain.analytics.metrics import compute_period_metrics
from backend.domain.analytics.rollup import (
    fetch_daily_rollups,
    rollup_all_tenants_for_day,
    rollup_row_to_daily_entry,
    rollup_tenant_day,
)

__all__ = [
    "compute_period_metrics",
    "fetch_daily_rollups",
    "rollup_all_tenants_for_day",
    "rollup_row_to_daily_entry",
    "rollup_tenant_day",
]
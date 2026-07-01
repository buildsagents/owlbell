"""Reporting domain — weekly ops / revenue-leakage reports."""

from backend.business.reporting.service import (
    ReportingService,
    estimate_opportunity_gbp,
    render_report_text,
)

__all__ = ["ReportingService", "estimate_opportunity_gbp", "render_report_text"]

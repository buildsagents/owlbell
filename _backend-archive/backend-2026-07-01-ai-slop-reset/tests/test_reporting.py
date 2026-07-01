"""Unit tests for the weekly report pure helpers (business/reporting/service.py)."""

from __future__ import annotations

import pytest

from backend.business.reporting.service import estimate_opportunity_gbp, render_report_text

pytestmark = pytest.mark.unit


def _report(**kw) -> dict:
    base = dict(
        period_start="2026-06-22",
        period_end="2026-06-29",
        calls_total=40,
        calls_answered=34,
        calls_missed=6,
        missed_recoveries=4,
        appointments_booked=9,
        reminders_sent=7,
        reviews_requested=5,
        quote_followups=3,
        quotes_accepted=2,
        estimated_opportunity_gbp=1000.0,
    )
    base.update(kw)
    return base


def test_estimate_opportunity_basic():
    assert estimate_opportunity_gbp(4, 250.0) == 1000.0


def test_estimate_opportunity_zero_and_negative_clamped():
    assert estimate_opportunity_gbp(0, 250.0) == 0.0
    assert estimate_opportunity_gbp(-3, 250.0) == 0.0
    assert estimate_opportunity_gbp(5, -10.0) == 0.0


def test_estimate_opportunity_rounds():
    assert estimate_opportunity_gbp(3, 99.999) == 300.0


def test_render_report_contains_key_metrics():
    text = render_report_text(_report(), "Acme Plumbing")
    assert "Acme Plumbing" in text
    assert "2026-06-22 to 2026-06-29" in text
    assert "Answered: 34 of 40" in text
    assert "Recovered by instant text-back: 4" in text
    assert "£1,000.00" in text
    assert "estimate" in text.lower()


def test_render_report_is_plain_multiline():
    text = render_report_text(_report(), "Acme Plumbing")
    assert "\n" in text
    # No unresolved format placeholders.
    assert "{" not in text and "}" not in text

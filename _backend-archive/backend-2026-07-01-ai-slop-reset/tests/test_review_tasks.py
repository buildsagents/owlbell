"""Unit tests for post-job review-request logic (workers/review_tasks.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from workers.review_tasks import _render_message, _review_due

pytestmark = pytest.mark.unit

_UTC = timezone.utc
_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
_URL = "https://g.page/r/acme/review"


def _appt(**kw) -> SimpleNamespace:
    base = dict(
        caller_number="+15551234567",
        caller_name="Sam",
        completed_at=_NOW - timedelta(hours=5),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _tenant(**kw) -> SimpleNamespace:
    cfg = {"google_review_url": _URL}
    cfg.update(kw.pop("config_json", {}))
    base = dict(config_json=cfg, business_name="Acme Plumbing", name="acme")
    base.update(kw)
    return SimpleNamespace(**base)


def test_due_in_window():
    assert _review_due(_appt(), _tenant(), _NOW) is True


def test_due_too_soon_after_completion():
    # completed 1h ago, default min delay is 2h.
    assert _review_due(_appt(completed_at=_NOW - timedelta(hours=1)), _tenant(), _NOW) is False


def test_due_too_old():
    # completed 8 days ago, default max age is 7 days.
    appt = _appt(completed_at=_NOW - timedelta(days=8))
    assert _review_due(appt, _tenant(), _NOW) is False


def test_due_requires_completed_at():
    assert _review_due(_appt(completed_at=None), _tenant(), _NOW) is False


def test_due_requires_review_url():
    tenant = SimpleNamespace(config_json={}, business_name="Acme", name="acme")
    assert _review_due(_appt(), tenant, _NOW) is False


def test_due_respects_disabled_flag():
    assert _review_due(_appt(), _tenant(config_json={"reviews_enabled": False}), _NOW) is False


def test_due_requires_caller_number():
    assert _review_due(_appt(caller_number=None), _tenant(), _NOW) is False


def test_due_handles_naive_completed_at():
    # DB may hand back a naive UTC datetime; it must still compare correctly.
    naive = (_NOW - timedelta(hours=5)).replace(tzinfo=None)
    assert _review_due(_appt(completed_at=naive), _tenant(), _NOW) is True


def test_due_custom_delay_and_age():
    tenant = _tenant(config_json={"review_min_delay_hours": 24, "review_max_age_hours": 48})
    assert _review_due(_appt(completed_at=_NOW - timedelta(hours=12)), tenant, _NOW) is False
    assert _review_due(_appt(completed_at=_NOW - timedelta(hours=36)), tenant, _NOW) is True


def test_render_message():
    msg = _render_message(_appt(), _tenant())
    assert "Acme Plumbing" in msg
    assert "Sam" in msg
    assert _URL in msg


def test_render_message_missing_name():
    assert "there" in _render_message(_appt(caller_name=None), _tenant())

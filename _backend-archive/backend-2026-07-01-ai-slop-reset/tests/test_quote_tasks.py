"""Unit tests for quote-follow-up logic (workers/quote_tasks.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from workers.quote_tasks import (
    _followup_due,
    _format_amount,
    _is_expired,
    _render_message,
)

pytestmark = pytest.mark.unit

_UTC = timezone.utc
_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)


def _quote(**kw) -> SimpleNamespace:
    base = dict(
        customer_number="+447700900123",
        customer_name="Sam",
        amount=Decimal("1250.50"),
        currency="GBP",
        sent_at=_NOW - timedelta(hours=50),
        last_followup_at=None,
        followup_count=0,
        expires_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _tenant(**kw) -> SimpleNamespace:
    base = dict(
        config_json={},
        business_name="Acme Plumbing",
        name="acme",
        business_phone="+447700900111",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_due_after_interval():
    assert _followup_due(_quote(), _tenant(), _NOW) is True


def test_not_due_before_interval():
    assert _followup_due(_quote(sent_at=_NOW - timedelta(hours=10)), _tenant(), _NOW) is False


def test_not_due_at_max_followups():
    assert _followup_due(_quote(followup_count=3), _tenant(), _NOW) is False


def test_cadence_anchors_on_last_followup():
    # Sent long ago but followed up recently -> not due yet.
    q = _quote(sent_at=_NOW - timedelta(days=10), last_followup_at=_NOW - timedelta(hours=5))
    assert _followup_due(q, _tenant(), _NOW) is False
    # Last follow-up now older than the interval -> due.
    q2 = _quote(sent_at=_NOW - timedelta(days=10), last_followup_at=_NOW - timedelta(hours=50))
    assert _followup_due(q2, _tenant(), _NOW) is True


def test_not_due_when_disabled():
    tenant = _tenant(config_json={"quote_followups_enabled": False})
    assert _followup_due(_quote(), tenant, _NOW) is False


def test_not_due_without_number():
    assert _followup_due(_quote(customer_number=None), _tenant(), _NOW) is False


def test_not_due_when_expired():
    q = _quote(expires_at=_NOW - timedelta(hours=1))
    assert _followup_due(q, _tenant(), _NOW) is False


def test_not_due_without_sent_at():
    assert _followup_due(_quote(sent_at=None), _tenant(), _NOW) is False


def test_custom_interval_and_max():
    tenant = _tenant(config_json={"quote_followup_interval_hours": 24, "quote_max_followups": 5})
    assert _followup_due(_quote(sent_at=_NOW - timedelta(hours=12)), tenant, _NOW) is False
    assert _followup_due(_quote(sent_at=_NOW - timedelta(hours=30)), tenant, _NOW) is True


def test_hard_cap_beats_generous_config():
    # Even if a tenant sets a huge max, the hard cap (10) still applies.
    tenant = _tenant(config_json={"quote_max_followups": 999})
    assert _followup_due(_quote(followup_count=10), tenant, _NOW) is False


def test_is_expired_handles_naive_and_none():
    assert _is_expired(_quote(expires_at=None), _NOW) is False
    assert _is_expired(_quote(expires_at=(_NOW - timedelta(hours=1)).replace(tzinfo=None)), _NOW) is True
    assert _is_expired(_quote(expires_at=_NOW + timedelta(hours=1)), _NOW) is False


def test_format_amount():
    assert _format_amount(_quote(amount=None)) == ""
    assert _format_amount(_quote(amount=Decimal("1250.5"))) == " for £1,250.50"
    # Currency-aware: falls back to the symbol map.
    assert _format_amount(_quote(amount=Decimal("99"), currency="USD")) == " for $99.00"


def test_render_message_with_amount_and_phone():
    msg = _render_message(_quote(), _tenant())
    assert "Acme Plumbing" in msg
    assert "Sam" in msg
    assert "£1,250.50" in msg
    assert "call +447700900111" in msg


def test_render_message_without_amount_or_phone():
    msg = _render_message(_quote(amount=None, customer_name=None), _tenant(business_phone=None))
    assert "there" in msg
    assert "£" not in msg
    assert "call" not in msg.lower()

"""Unit tests for appointment reminder logic (workers/reminder_tasks.py).

Covers the pure helpers — timezone conversion, the send-decision window, and
message rendering — without touching Postgres.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest

from workers.reminder_tasks import (
    _appointment_start_utc,
    _format_time,
    _reminder_due,
    _render_message,
)

pytestmark = pytest.mark.unit

_UTC = timezone.utc


def _appt(**kw) -> SimpleNamespace:
    base = dict(
        timezone="UTC",
        scheduled_date=date(2026, 7, 2),
        start_time=time(14, 0),
        caller_number="+15551234567",
        caller_name="Sam",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _tenant(**kw) -> SimpleNamespace:
    base = dict(
        config_json={},
        business_timezone="UTC",
        business_name="Acme Plumbing",
        name="acme",
        business_phone="+15550001111",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _appt_in(now: datetime, delta: timedelta, **kw) -> SimpleNamespace:
    """Appointment whose (UTC) start is ``now + delta``."""
    start = now + delta
    return _appt(
        timezone="UTC",
        scheduled_date=start.date(),
        start_time=start.time().replace(microsecond=0),
        **kw,
    )


@pytest.mark.parametrize(
    "t,expected",
    [
        (time(9, 5), "9:05am"),
        (time(14, 30), "2:30pm"),
        (time(0, 0), "12:00am"),
        (time(12, 0), "12:00pm"),
    ],
)
def test_format_time(t, expected):
    assert _format_time(t) == expected


def test_start_utc_converts_timezone():
    # 2:00 PM in America/New_York on a July (EDT, UTC-4) date -> 18:00 UTC.
    appt = _appt(timezone="America/New_York")
    assert _appointment_start_utc(appt, None) == datetime(2026, 7, 2, 18, 0, tzinfo=_UTC)


def test_start_utc_invalid_timezone_falls_back_to_utc():
    got = _appointment_start_utc(_appt(timezone="Not/AZone"), None)
    assert got == datetime(2026, 7, 2, 14, 0, tzinfo=_UTC)


def test_due_inside_window():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    assert _reminder_due(_appt_in(now, timedelta(hours=12)), _tenant(), now) is True


def test_due_outside_window_is_false():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    assert _reminder_due(_appt_in(now, timedelta(hours=30)), _tenant(), now) is False


def test_due_past_appointment_is_false():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    assert _reminder_due(_appt_in(now, timedelta(hours=-1)), _tenant(), now) is False


def test_due_respects_disabled_flag():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    tenant = _tenant(config_json={"reminders_enabled": False})
    assert _reminder_due(_appt_in(now, timedelta(hours=12)), tenant, now) is False


def test_due_requires_caller_number():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    appt = _appt_in(now, timedelta(hours=12), caller_number=None)
    assert _reminder_due(appt, _tenant(), now) is False


def test_due_honours_custom_lead_hours():
    now = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)
    tenant = _tenant(config_json={"reminder_lead_hours": 2})
    assert _reminder_due(_appt_in(now, timedelta(hours=3)), tenant, now) is False
    assert _reminder_due(_appt_in(now, timedelta(hours=1)), tenant, now) is True


def test_render_message_with_phone():
    msg = _render_message(_appt(), _tenant())
    assert "Acme Plumbing" in msg
    assert "Sam" in msg
    assert "+15550001111" in msg
    assert "2 July" in msg
    assert "2:00pm" in msg


def test_render_message_no_phone_and_no_name():
    msg = _render_message(_appt(caller_name=None), _tenant(business_phone=None))
    assert "there" in msg
    assert "call" not in msg.lower()

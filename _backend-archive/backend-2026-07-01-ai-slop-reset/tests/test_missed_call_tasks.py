"""Unit tests for missed-call text-back logic (workers/missed_call_tasks.py)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.db.models.enums import CallDirection, CallStatus
from workers.missed_call_tasks import _is_missed, _render_message, _textback_due

pytestmark = pytest.mark.unit

_UTC = timezone.utc
_NOW = datetime(2026, 7, 1, 12, 0, tzinfo=_UTC)


def _call(**kw) -> SimpleNamespace:
    base = dict(
        direction=CallDirection.INBOUND,
        status=CallStatus.NO_ANSWER,
        caller_number="+447700900123",
        caller_name="Sam",
        metadata_json={},
        voicemail_left=False,
        started_at=_NOW - timedelta(minutes=2),
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _tenant(**kw) -> SimpleNamespace:
    base = dict(config_json={}, business_name="Acme Plumbing", name="acme")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.mark.parametrize("status", [CallStatus.NO_ANSWER, CallStatus.FAILED, CallStatus.VOICEMAIL])
def test_due_for_missed_statuses(status):
    assert _textback_due(_call(status=status), _tenant(), _NOW) is True


def test_due_when_voicemail_left_even_if_completed():
    call = _call(status=CallStatus.COMPLETED, voicemail_left=True)
    assert _is_missed(call) is True
    assert _textback_due(call, _tenant(), _NOW) is True


def test_not_due_for_answered_call():
    call = _call(status=CallStatus.COMPLETED, voicemail_left=False)
    assert _textback_due(call, _tenant(), _NOW) is False


def test_not_due_for_outbound():
    assert _textback_due(_call(direction=CallDirection.OUTBOUND), _tenant(), _NOW) is False


def test_not_due_when_already_sent():
    call = _call(metadata_json={"text_back_sent_at": _NOW.isoformat()})
    assert _textback_due(call, _tenant(), _NOW) is False


def test_not_due_when_disabled():
    tenant = _tenant(config_json={"missed_call_textback_enabled": False})
    assert _textback_due(_call(), tenant, _NOW) is False


def test_not_due_without_caller_number():
    assert _textback_due(_call(caller_number=None), _tenant(), _NOW) is False


def test_not_due_when_too_old():
    # Default max age is 360 min; this call started 7h ago.
    assert _textback_due(_call(started_at=_NOW - timedelta(hours=7)), _tenant(), _NOW) is False


def test_custom_max_age():
    tenant = _tenant(config_json={"missed_call_max_age_minutes": 10})
    assert _textback_due(_call(started_at=_NOW - timedelta(minutes=5)), tenant, _NOW) is True
    assert _textback_due(_call(started_at=_NOW - timedelta(minutes=15)), tenant, _NOW) is False


def test_handles_naive_started_at():
    call = _call(started_at=(_NOW - timedelta(minutes=2)).replace(tzinfo=None))
    assert _textback_due(call, _tenant(), _NOW) is True


def test_render_message():
    msg = _render_message(_call(), _tenant())
    assert "Acme Plumbing" in msg
    assert "Sam" in msg


def test_render_message_missing_name():
    assert "there" in _render_message(_call(caller_name=None), _tenant())

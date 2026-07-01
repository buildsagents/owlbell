"""Weekly Ops Report — aggregate a client's week and render it (owlbell blueprint P1).

`ReportingService.build_weekly_report` aggregates the metrics; `render_report_text`
and `estimate_opportunity_gbp` are pure helpers (unit-tested without a DB) shared
by the weekly email task and, later, the dashboard Overview/Reports views.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import Appointment, NotificationLog, Quote
from backend.db.models.call import Call
from backend.db.models.enums import CallDirection, CallStatus, QuoteStatus

logger = structlog.get_logger(__name__)

# Notification event types recorded by the SMS automations.
_EVT_TEXTBACK = "missed_call.textback"
_EVT_REMINDER = "appointment.reminder"
_EVT_REVIEW = "review.request"
_EVT_QUOTE = "quote.followup"

_MISSED_STATUSES = [CallStatus.NO_ANSWER, CallStatus.FAILED, CallStatus.VOICEMAIL]
_ANSWERED_STATUSES = [CallStatus.ANSWERED, CallStatus.COMPLETED]

# Default estimated value of one recovered plumbing job (GBP), tenant-overridable.
DEFAULT_AVG_JOB_VALUE_GBP = 250.0


def estimate_opportunity_gbp(missed_recoveries: int, avg_job_value: float) -> float:
    """Estimated £ recovered from texting back missed callers (labelled an estimate)."""
    return round(max(missed_recoveries, 0) * max(avg_job_value, 0.0), 2)


def render_report_text(report: dict[str, Any], business_name: str) -> str:
    """Render a weekly report dict into a plain-text email body."""
    lines = [
        f"Hi {business_name} team,",
        "",
        "Here is what Owlbell handled for you last week "
        f"({report['period_start']} to {report['period_end']}).",
        "",
        "Calls",
        f"  Answered: {report['calls_answered']} of {report['calls_total']}",
        f"  Missed: {report['calls_missed']}",
        f"  Recovered by instant text-back: {report['missed_recoveries']}",
        "",
        "Follow-up",
        f"  Appointments booked: {report['appointments_booked']}",
        f"  Appointment reminders sent: {report['reminders_sent']}",
        f"  Quote follow-ups sent: {report['quote_followups']}",
        f"  Quotes accepted: {report['quotes_accepted']}",
        f"  Review requests sent: {report['reviews_requested']}",
        "",
        f"Estimated recovered opportunity: £{report['estimated_opportunity_gbp']:,.2f}",
        f"(An estimate from {report['missed_recoveries']} recovered calls at your "
        "average job value. Not guaranteed revenue.)",
        "",
        "Any questions, just reply to this email.",
        "Owlbell",
    ]
    return "\n".join(lines)


class ReportingService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id

    async def _count(self, model: Any, *conditions: Any) -> int:
        stmt = (
            select(func.count())
            .select_from(model)
            .where(model.tenant_id == self._tenant_id, *conditions)
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def _event_counts(self, start: datetime, end: datetime) -> dict[str, int]:
        stmt = (
            select(NotificationLog.event_type, func.count())
            .where(
                NotificationLog.tenant_id == self._tenant_id,
                NotificationLog.created_at >= start,
                NotificationLog.created_at < end,
            )
            .group_by(NotificationLog.event_type)
        )
        rows = (await self._session.execute(stmt)).all()
        return {event_type: int(n) for event_type, n in rows}

    async def build_weekly_report(
        self, start: datetime, end: datetime, avg_job_value: float = DEFAULT_AVG_JOB_VALUE_GBP
    ) -> dict[str, Any]:
        """Aggregate metrics for ``[start, end)`` into a report dict."""
        calls_total = await self._count(
            Call, Call.direction == CallDirection.INBOUND,
            Call.started_at >= start, Call.started_at < end,
        )
        calls_answered = await self._count(
            Call, Call.direction == CallDirection.INBOUND,
            Call.started_at >= start, Call.started_at < end,
            or_(Call.status.in_(_ANSWERED_STATUSES), Call.ai_handled.is_(True)),
        )
        calls_missed = await self._count(
            Call, Call.direction == CallDirection.INBOUND,
            Call.started_at >= start, Call.started_at < end,
            or_(Call.status.in_(_MISSED_STATUSES), Call.voicemail_left.is_(True)),
        )
        appointments_booked = await self._count(
            Appointment, Appointment.created_at >= start, Appointment.created_at < end,
        )
        quotes_accepted = await self._count(
            Quote, Quote.status == QuoteStatus.ACCEPTED,
            Quote.accepted_at >= start, Quote.accepted_at < end,
        )

        events = await self._event_counts(start, end)
        missed_recoveries = events.get(_EVT_TEXTBACK, 0)

        return {
            "period_start": start.date().isoformat(),
            "period_end": end.date().isoformat(),
            "calls_total": calls_total,
            "calls_answered": calls_answered,
            "calls_missed": calls_missed,
            "missed_recoveries": missed_recoveries,
            "appointments_booked": appointments_booked,
            "reminders_sent": events.get(_EVT_REMINDER, 0),
            "reviews_requested": events.get(_EVT_REVIEW, 0),
            "quote_followups": events.get(_EVT_QUOTE, 0),
            "quotes_accepted": quotes_accepted,
            "estimated_opportunity_gbp": estimate_opportunity_gbp(missed_recoveries, avg_job_value),
        }

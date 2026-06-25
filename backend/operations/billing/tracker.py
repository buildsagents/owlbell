"""operations/billing/tracker.py - Usage tracking and metering.

Tracks billable usage per tenant: call minutes, AI tokens, API calls.
Emits events for aggregation, enforces plan limits.

Design: Event-sourced metering. Every billable action emits an event;
aggregators consume events. Graceful degradation: if tracking fails,
calls continue; we reconcile later.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class ActionType(str, Enum):
    """Types of billable actions."""
    CALL_INBOUND = "call_inbound"
    CALL_OUTBOUND = "call_outbound"
    CALL_MINUTE = "call_minute"
    STT_REQUEST = "stt_request"
    STT_AUDIO_SECOND = "stt_audio_second"
    LLM_REQUEST = "llm_request"
    LLM_TOKEN_INPUT = "llm_token_input"
    LLM_TOKEN_OUTPUT = "llm_token_output"
    TTS_REQUEST = "tts_request"
    TTS_CHARACTER = "tts_character"
    TRANSCRIPTION = "transcription"
    WEBHOOK_DELIVERY = "webhook_delivery"
    API_REQUEST = "api_request"


# Maps each billable ActionType to how it is stored in the ``usage_records``
# table: (event_type, event_subtype, unit). Used when persisting to Postgres.
_ACTION_DB_MAP: Dict["ActionType", tuple[str, Optional[str], str]] = {
    ActionType.CALL_INBOUND: ("call", "inbound", "calls"),
    ActionType.CALL_OUTBOUND: ("call", "outbound", "calls"),
    ActionType.CALL_MINUTE: ("call", "minute", "minutes"),
    ActionType.STT_REQUEST: ("stt", "request", "requests"),
    ActionType.STT_AUDIO_SECOND: ("stt", "audio", "seconds"),
    ActionType.LLM_REQUEST: ("llm", "request", "requests"),
    ActionType.LLM_TOKEN_INPUT: ("llm", "input", "tokens"),
    ActionType.LLM_TOKEN_OUTPUT: ("llm", "output", "tokens"),
    ActionType.TTS_REQUEST: ("tts", "request", "requests"),
    ActionType.TTS_CHARACTER: ("tts", "character", "characters"),
    ActionType.TRANSCRIPTION: ("transcription", None, "requests"),
    ActionType.WEBHOOK_DELIVERY: ("webhook", "delivery", "requests"),
    ActionType.API_REQUEST: ("api", "request", "requests"),
}


# Use dict for simple storage where dataclasses aren't needed


class UsageEvent:
    """A single usage event for metering.

    Attributes:
        tenant_id: The tenant UUID
        action_type: Type of billable action
        quantity: Amount consumed (calls, minutes, tokens, etc.)
        period: YYYY-MM period string for aggregation
        source_type: Source of the action (call, api, webhook, system)
        source_id: Reference ID (call_id, endpoint, etc.)
        metadata: Additional context
        timestamp: When the event occurred
    """

    def __init__(
        self,
        tenant_id: uuid.UUID,
        action_type: ActionType,
        quantity: float = 1.0,
        period: Optional[str] = None,
        source_type: str = "call",
        source_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.action_type = action_type
        self.quantity = quantity
        self.period = period or datetime.utcnow().strftime("%Y-%m")
        self.source_type = source_type
        self.source_id = source_id
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "action_type": self.action_type.value,
            "quantity": self.quantity,
            "period": self.period,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class UsageSnapshot:
    """Pre-computed daily usage totals per tenant.

    Updated by daily rollup job. Dashboard reads from here, not raw records.
    """

    def __init__(
        self,
        tenant_id: uuid.UUID,
        period: str,
        total_calls: int = 0,
        total_minutes: float = 0.0,
        total_stt_seconds: float = 0.0,
        total_llm_input_tokens: int = 0,
        total_llm_output_tokens: int = 0,
        total_tts_characters: int = 0,
        total_api_requests: int = 0,
    ):
        self.tenant_id = tenant_id
        self.period = period
        self.total_calls = total_calls
        self.total_minutes = total_minutes
        self.total_stt_seconds = total_stt_seconds
        self.total_llm_input_tokens = total_llm_input_tokens
        self.total_llm_output_tokens = total_llm_output_tokens
        self.total_tts_characters = total_tts_characters
        self.total_api_requests = total_api_requests
        self.computed_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "period": self.period,
            "total_calls": self.total_calls,
            "total_minutes": self.total_minutes,
            "total_stt_seconds": self.total_stt_seconds,
            "total_llm_input_tokens": self.total_llm_input_tokens,
            "total_llm_output_tokens": self.total_llm_output_tokens,
            "total_tts_characters": self.total_tts_characters,
            "total_api_requests": self.total_api_requests,
            "computed_at": self.computed_at.isoformat(),
        }


class BillingSnapshot:
    """Monthly billing state per tenant."""

    def __init__(
        self,
        tenant_id: uuid.UUID,
        period: str,
        plan_tier: str,
        calls_used: int = 0,
        minutes_used: float = 0.0,
        tokens_used: int = 0,
        call_limit: int = 100,
        call_limit_reached: bool = False,
        overage_calls: int = 0,
        overage_minutes: float = 0.0,
        overage_estimated_cost: float = 0.0,
    ):
        self.tenant_id = tenant_id
        self.period = period
        self.plan_tier = plan_tier
        self.calls_used = calls_used
        self.minutes_used = minutes_used
        self.tokens_used = tokens_used
        self.call_limit = call_limit
        self.call_limit_reached = call_limit_reached
        self.overage_calls = overage_calls
        self.overage_minutes = overage_minutes
        self.overage_estimated_cost = overage_estimated_cost
        self.is_finalized = False
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "period": self.period,
            "plan_tier": self.plan_tier,
            "calls_used": self.calls_used,
            "minutes_used": self.minutes_used,
            "tokens_used": self.tokens_used,
            "call_limit": self.call_limit,
            "call_limit_reached": self.call_limit_reached,
            "overage_calls": self.overage_calls,
            "overage_minutes": self.overage_minutes,
            "overage_estimated_cost": self.overage_estimated_cost,
            "is_finalized": self.is_finalized,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# -- Usage Tracker --------------------------------------------------------


class UsageTracker:
    """Usage tracking and metering service.

    Usage:
        tracker = UsageTracker(session_maker=get_session_maker())
        await tracker.track_call_minutes(tenant_id, duration_seconds=120)
        await tracker.track_llm_tokens(tenant_id, input_tokens=100, output_tokens=50)
        summary = await tracker.get_usage_summary(tenant_id, "2025-01")

    When ``session_maker`` is provided, every event is persisted to the
    ``usage_records`` table and aggregation reads from Postgres. Without it,
    the tracker keeps everything in process memory (used by unit tests).
    """

    def __init__(
        self,
        session_maker: Optional[Callable[[], Any]] = None,
        plan_manager: Optional[Any] = None,
    ):
        self.session_maker = session_maker
        self.plan_manager = plan_manager
        self._events: List[UsageEvent] = []
        self._snapshots: Dict[str, UsageSnapshot] = {}
        self._billing: Dict[str, BillingSnapshot] = {}
        self._tenant_counters: Dict[str, Dict[str, Any]] = {}

    @property
    def persistent(self) -> bool:
        """True when events are written through to Postgres."""
        return self.session_maker is not None

    # -- Event Tracking ---------------------------------------------------

    async def emit_event(self, event: UsageEvent) -> None:
        """Emit a usage event.

        Fire-and-forget: the in-memory counters are always updated for fast
        limit checks, and — when a session maker is configured — the event is
        also written to ``usage_records``. If tracking fails, the error is
        logged but never raised (calls must continue; we reconcile later).
        """
        try:
            self._events.append(event)
            self._update_counters(event)

            if self.session_maker is not None:
                await self._persist_event(event)

            logger.debug(
                "usage.event",
                tenant_id=str(event.tenant_id),
                action=event.action_type.value,
                quantity=event.quantity,
                persisted=self.session_maker is not None,
            )
        except Exception as exc:
            logger.error(
                "usage.event_failed",
                tenant_id=str(event.tenant_id),
                error=str(exc),
            )

    async def _persist_event(self, event: UsageEvent) -> None:
        """Write a single usage event to the ``usage_records`` table."""
        from backend.db.models.operations import UsageRecord

        event_type, event_subtype, unit = _ACTION_DB_MAP.get(
            event.action_type, (event.action_type.value, None, "units")
        )
        ts = event.timestamp
        call_id = None
        if event.source_type == "call" and event.source_id:
            try:
                call_id = uuid.UUID(str(event.source_id))
            except (ValueError, AttributeError, TypeError):
                call_id = None

        record = UsageRecord(
            id=uuid.uuid4(),
            tenant_id=event.tenant_id,
            event_type=event_type,
            event_subtype=event_subtype,
            call_id=call_id,
            quantity=Decimal(str(event.quantity)),
            unit=unit,
            cost_per_unit=Decimal("0.0"),
            total_cost=Decimal("0.0"),
            period_hour=ts.replace(minute=0, second=0, microsecond=0),
            period_day=ts.date(),
            period_month=event.period,
            created_at=ts,
        )
        async with self.session_maker() as session:
            session.add(record)
            await session.commit()

    async def track_call_start(self, tenant_id: uuid.UUID, call_id: str) -> None:
        """Track an inbound call start."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.CALL_INBOUND,
            quantity=1.0,
            source_type="call",
            source_id=call_id,
            metadata={"event": "call_started"},
        ))

    async def track_call_minutes(
        self, tenant_id: uuid.UUID, duration_seconds: float, call_id: str = ""
    ) -> None:
        """Track call duration in minutes."""
        minutes = duration_seconds / 60.0
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.CALL_MINUTE,
            quantity=round(minutes, 2),
            source_type="call",
            source_id=call_id,
        ))

    async def track_stt(
        self, tenant_id: uuid.UUID, audio_seconds: float, call_id: str = ""
    ) -> None:
        """Track speech-to-text processing."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.STT_AUDIO_SECOND,
            quantity=round(audio_seconds, 2),
            source_type="call",
            source_id=call_id,
        ))

    async def track_llm_tokens(
        self,
        tenant_id: uuid.UUID,
        input_tokens: int,
        output_tokens: int,
        call_id: str = "",
    ) -> None:
        """Track LLM token usage."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.LLM_TOKEN_INPUT,
            quantity=float(input_tokens),
            source_type="call",
            source_id=call_id,
        ))
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.LLM_TOKEN_OUTPUT,
            quantity=float(output_tokens),
            source_type="call",
            source_id=call_id,
        ))

    async def track_tts(
        self, tenant_id: uuid.UUID, characters: int, call_id: str = ""
    ) -> None:
        """Track text-to-speech character usage."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.TTS_CHARACTER,
            quantity=float(characters),
            source_type="call",
            source_id=call_id,
        ))

    async def track_api_request(
        self, tenant_id: uuid.UUID, endpoint: str
    ) -> None:
        """Track a dashboard/API request."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.API_REQUEST,
            quantity=1.0,
            source_type="api",
            source_id=endpoint,
        ))

    async def track_webhook_delivery(
        self, tenant_id: uuid.UUID, webhook_id: str, event_type: str
    ) -> None:
        """Track webhook delivery."""
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=ActionType.WEBHOOK_DELIVERY,
            quantity=1.0,
            source_type="webhook",
            source_id=webhook_id,
            metadata={"event_type": event_type},
        ))

    # -- Counters ---------------------------------------------------------

    def _update_counters(self, event: UsageEvent) -> None:
        """Update in-memory counters for near-realtime checking."""
        key = f"{event.tenant_id}:{event.period}"
        if key not in self._tenant_counters:
            self._tenant_counters[key] = {
                "calls": 0,
                "minutes": 0.0,
                "tokens": 0,
                "api_requests": 0,
            }

        counter = self._tenant_counters[key]
        if event.action_type == ActionType.CALL_INBOUND:
            counter["calls"] += int(event.quantity)
        elif event.action_type == ActionType.CALL_MINUTE:
            counter["minutes"] += event.quantity
        elif event.action_type in (ActionType.LLM_TOKEN_INPUT, ActionType.LLM_TOKEN_OUTPUT):
            counter["tokens"] += int(event.quantity)
        elif event.action_type == ActionType.API_REQUEST:
            counter["api_requests"] += int(event.quantity)

    # -- Aggregation ------------------------------------------------------

    async def get_usage_summary(
        self, tenant_id: uuid.UUID, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get usage summary for a tenant."""
        period = period or datetime.utcnow().strftime("%Y-%m")
        key = f"{tenant_id}:{period}"

        if self.session_maker is not None:
            counter = await self._db_counters(tenant_id, period)
        else:
            counter = self._tenant_counters.get(key, {
                "calls": 0, "minutes": 0.0, "tokens": 0, "api_requests": 0,
            })

        billing_key = f"{tenant_id}:{period}"
        billing = self._billing.get(billing_key)

        return {
            "tenant_id": str(tenant_id),
            "period": period,
            "calls_used": counter["calls"],
            "minutes_used": round(counter["minutes"], 2),
            "tokens_used": counter["tokens"],
            "api_requests": counter["api_requests"],
            "billing": billing.to_dict() if billing else None,
        }

    async def _db_counters(self, tenant_id: uuid.UUID, period: str) -> Dict[str, Any]:
        """Aggregate the headline counters for a tenant/period from Postgres."""
        from sqlalchemy import func, select

        from backend.db.models.operations import UsageRecord

        counter = {"calls": 0, "minutes": 0.0, "tokens": 0, "api_requests": 0}
        async with self.session_maker() as session:
            stmt = (
                select(
                    UsageRecord.event_type,
                    UsageRecord.event_subtype,
                    func.coalesce(func.sum(UsageRecord.quantity), 0),
                )
                .where(
                    UsageRecord.tenant_id == tenant_id,
                    UsageRecord.period_month == period,
                )
                .group_by(UsageRecord.event_type, UsageRecord.event_subtype)
            )
            result = await session.execute(stmt)
            for event_type, subtype, total in result.all():
                qty = float(total or 0)
                if event_type == "call" and subtype in ("inbound", "outbound"):
                    counter["calls"] += int(qty)
                elif event_type == "call" and subtype == "minute":
                    counter["minutes"] += qty
                elif event_type == "llm" and subtype in ("input", "output"):
                    counter["tokens"] += int(qty)
                elif event_type == "api":
                    counter["api_requests"] += int(qty)
        counter["minutes"] = round(counter["minutes"], 2)
        return counter

    async def get_usage_breakdown(
        self, tenant_id: uuid.UUID, period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get detailed usage breakdown by action type."""
        period = period or datetime.utcnow().strftime("%Y-%m")

        if self.session_maker is not None:
            from sqlalchemy import func, select

            from backend.db.models.operations import UsageRecord

            by_action: Dict[str, Dict[str, float]] = {}
            total_events = 0
            async with self.session_maker() as session:
                stmt = (
                    select(
                        UsageRecord.event_type,
                        UsageRecord.event_subtype,
                        func.count(UsageRecord.id),
                        func.coalesce(func.sum(UsageRecord.quantity), 0),
                    )
                    .where(
                        UsageRecord.tenant_id == tenant_id,
                        UsageRecord.period_month == period,
                    )
                    .group_by(UsageRecord.event_type, UsageRecord.event_subtype)
                )
                result = await session.execute(stmt)
                for event_type, subtype, count, total in result.all():
                    action = f"{event_type}:{subtype}" if subtype else event_type
                    by_action[action] = {
                        "count": int(count),
                        "quantity": float(total or 0),
                    }
                    total_events += int(count)
            return {
                "tenant_id": str(tenant_id),
                "period": period,
                "by_action_type": by_action,
                "total_events": total_events,
            }

        by_action: Dict[str, Dict[str, float]] = {}
        for event in self._events:
            if event.tenant_id == tenant_id and event.period == period:
                action = event.action_type.value
                if action not in by_action:
                    by_action[action] = {"count": 0, "quantity": 0.0}
                by_action[action]["count"] += 1
                by_action[action]["quantity"] += event.quantity

        return {
            "tenant_id": str(tenant_id),
            "period": period,
            "by_action_type": by_action,
            "total_events": len(self._events),
        }

    # -- Limit Checking ---------------------------------------------------

    async def is_within_call_limit(
        self, tenant_id: uuid.UUID, plan_call_limit: int, period: Optional[str] = None
    ) -> bool:
        """Check if tenant is within call limit."""
        period = period or datetime.utcnow().strftime("%Y-%m")
        if self.session_maker is not None:
            counter = await self._db_counters(tenant_id, period)
        else:
            key = f"{tenant_id}:{period}"
            counter = self._tenant_counters.get(key, {"calls": 0})
        return counter["calls"] < plan_call_limit

    async def get_remaining_calls(
        self, tenant_id: uuid.UUID, plan_call_limit: int, period: Optional[str] = None
    ) -> int:
        """Get remaining calls for tenant."""
        period = period or datetime.utcnow().strftime("%Y-%m")
        if self.session_maker is not None:
            counter = await self._db_counters(tenant_id, period)
        else:
            key = f"{tenant_id}:{period}"
            counter = self._tenant_counters.get(key, {"calls": 0})
        return max(0, plan_call_limit - counter["calls"])

    # -- Snapshots --------------------------------------------------------

    async def compute_snapshot(self, tenant_id: uuid.UUID, period: str) -> UsageSnapshot:
        """Compute usage snapshot for a tenant and period."""
        snapshot = UsageSnapshot(tenant_id=tenant_id, period=period)

        if self.session_maker is not None:
            from sqlalchemy import func, select

            from backend.db.models.operations import UsageRecord

            async with self.session_maker() as session:
                stmt = (
                    select(
                        UsageRecord.event_type,
                        UsageRecord.event_subtype,
                        func.coalesce(func.sum(UsageRecord.quantity), 0),
                    )
                    .where(
                        UsageRecord.tenant_id == tenant_id,
                        UsageRecord.period_month == period,
                    )
                    .group_by(UsageRecord.event_type, UsageRecord.event_subtype)
                )
                result = await session.execute(stmt)
                for event_type, subtype, total in result.all():
                    qty = float(total or 0)
                    if event_type == "call" and subtype in ("inbound", "outbound"):
                        snapshot.total_calls += int(qty)
                    elif event_type == "call" and subtype == "minute":
                        snapshot.total_minutes += qty
                    elif event_type == "stt" and subtype == "audio":
                        snapshot.total_stt_seconds += qty
                    elif event_type == "llm" and subtype == "input":
                        snapshot.total_llm_input_tokens += int(qty)
                    elif event_type == "llm" and subtype == "output":
                        snapshot.total_llm_output_tokens += int(qty)
                    elif event_type == "tts" and subtype == "character":
                        snapshot.total_tts_characters += int(qty)
                    elif event_type == "api":
                        snapshot.total_api_requests += int(qty)
            self._snapshots[f"{tenant_id}:{period}"] = snapshot
            return snapshot

        for event in self._events:
            if event.tenant_id == tenant_id and event.period == period:
                if event.action_type == ActionType.CALL_INBOUND:
                    snapshot.total_calls += int(event.quantity)
                elif event.action_type == ActionType.CALL_MINUTE:
                    snapshot.total_minutes += event.quantity
                elif event.action_type == ActionType.STT_AUDIO_SECOND:
                    snapshot.total_stt_seconds += event.quantity
                elif event.action_type == ActionType.LLM_TOKEN_INPUT:
                    snapshot.total_llm_input_tokens += int(event.quantity)
                elif event.action_type == ActionType.LLM_TOKEN_OUTPUT:
                    snapshot.total_llm_output_tokens += int(event.quantity)
                elif event.action_type == ActionType.TTS_CHARACTER:
                    snapshot.total_tts_characters += int(event.quantity)
                elif event.action_type == ActionType.API_REQUEST:
                    snapshot.total_api_requests += int(event.quantity)

        self._snapshots[f"{tenant_id}:{period}"] = snapshot
        return snapshot

    async def get_snapshot(
        self, tenant_id: uuid.UUID, period: str
    ) -> Optional[UsageSnapshot]:
        """Get cached snapshot or compute new one."""
        key = f"{tenant_id}:{period}"
        snapshot = self._snapshots.get(key)
        if snapshot:
            return snapshot
        return await self.compute_snapshot(tenant_id, period)

    # -- Billing ----------------------------------------------------------

    async def update_billing_snapshot(
        self, tenant_id: uuid.UUID, period: str, plan_tier: str, call_limit: int
    ) -> BillingSnapshot:
        """Update billing snapshot from current counters."""
        key = f"{tenant_id}:{period}"
        counter = self._tenant_counters.get(key, {"calls": 0, "minutes": 0.0, "tokens": 0})

        calls_used = counter["calls"]
        call_limit_reached = calls_used >= call_limit
        overage_calls = max(0, calls_used - call_limit)

        billing = BillingSnapshot(
            tenant_id=tenant_id,
            period=period,
            plan_tier=plan_tier,
            calls_used=calls_used,
            minutes_used=counter["minutes"],
            tokens_used=counter["tokens"],
            call_limit=call_limit,
            call_limit_reached=call_limit_reached,
            overage_calls=overage_calls,
        )

        self._billing[key] = billing
        return billing

    # -- Event Stream -----------------------------------------------------

    async def get_recent_events(
        self, tenant_id: uuid.UUID, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get recent events for a tenant."""
        if self.session_maker is not None:
            from sqlalchemy import select

            from backend.db.models.operations import UsageRecord

            async with self.session_maker() as session:
                stmt = (
                    select(UsageRecord)
                    .where(UsageRecord.tenant_id == tenant_id)
                    .order_by(UsageRecord.created_at.desc())
                    .limit(limit)
                )
                result = await session.execute(stmt)
                return [
                    {
                        "id": str(r.id),
                        "tenant_id": str(r.tenant_id),
                        "event_type": r.event_type,
                        "event_subtype": r.event_subtype,
                        "quantity": float(r.quantity),
                        "unit": r.unit,
                        "call_id": str(r.call_id) if r.call_id else None,
                        "period": r.period_month,
                        "timestamp": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in result.scalars().all()
                ]

        events = [
            e.to_dict() for e in reversed(self._events)
            if e.tenant_id == tenant_id
        ]
        return events[:limit]

    # -- Convenience ------------------------------------------------------

    async def record_call_completed(
        self,
        tenant_id: uuid.UUID,
        call_id: str = "",
        duration_seconds: float = 0.0,
        llm_input_tokens: int = 0,
        llm_output_tokens: int = 0,
        direction: str = "inbound",
    ) -> None:
        """Record all billable usage for a completed call in one shot.

        Called from the post-call path (``on_call_ended``) so a finished call
        produces its call, minute, and token usage records together.
        """
        action = (
            ActionType.CALL_OUTBOUND if direction == "outbound"
            else ActionType.CALL_INBOUND
        )
        await self.emit_event(UsageEvent(
            tenant_id=tenant_id,
            action_type=action,
            quantity=1.0,
            source_type="call",
            source_id=call_id,
        ))
        if duration_seconds > 0:
            await self.track_call_minutes(tenant_id, duration_seconds, call_id)
        if llm_input_tokens or llm_output_tokens:
            await self.track_llm_tokens(
                tenant_id, llm_input_tokens, llm_output_tokens, call_id
            )

    async def get_event_stream(
        self, tenant_id: uuid.UUID, action_type: Optional[ActionType] = None
    ) -> List[Dict[str, Any]]:
        """Get filtered event stream."""
        events = self._events
        if action_type:
            events = [e for e in events if e.action_type == action_type]
        return [e.to_dict() for e in events if e.tenant_id == tenant_id]

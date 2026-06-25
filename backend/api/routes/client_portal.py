"""api/routes/client_portal.py - Client portal routes (limited self-service).

Endpoints (mounted at /api/v1/portal by api/main.py):
    GET  /me               -> current client's account info
    GET  /calls             -> client's own calls
    GET  /calls/{id}        -> single call detail + transcript
    GET  /analytics         -> client's usage analytics
    GET  /settings          -> client's current configuration
    PUT  /settings          -> update limited settings (greeting, hours, notifications)
    GET  /billing           -> client's billing summary + link to Stripe portal
    GET  /onboarding        -> client's onboarding checklist status
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import cast, Date, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentUser, get_db_session
from backend.db.models.ai import Transcript
from backend.db.models.business import Appointment, BusinessHours, FAQEntry
from backend.db.models.call import Call
from backend.db.models.tenant import Tenant, TenantConfig
from backend.db.models.enums import CallResult, CallStatus, PlanTier

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/portal", tags=["Client Portal"])

DBSession = Depends(get_db_session)

PLAN_PRICES = {
    PlanTier.FREE: 0,
    PlanTier.STARTER: 297,
    PlanTier.PROFESSIONAL: 797,
    PlanTier.ENTERPRISE: 2000,
}

ONBOARDING_STEPS = [
    {"name": "Account created", "description": "Your account is set up"},
    {"name": "Business info submitted", "description": "Hours, services, and FAQs received"},
    {"name": "AI configured", "description": "Your receptionist is being built"},
    {"name": "Phone number ready", "description": "Number assigned or forwarding set up"},
    {"name": "Test calls complete", "description": "You've heard it answer as your business"},
    {"name": "Go live", "description": "Calls are being answered by Owlbell"},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_tenant(db: AsyncSession, tenant_id: UUID) -> Tenant:
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


async def _get_tenant_config(db: AsyncSession, tenant_id: UUID) -> TenantConfig:
    result = await db.execute(select(TenantConfig).where(TenantConfig.tenant_id == tenant_id))
    cfg = result.scalar_one_or_none()
    if cfg is None:
        cfg = TenantConfig(tenant_id=tenant_id)
        db.add(cfg)
        await db.flush()
    return cfg


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PortalAccount(BaseModel):
    id: str
    name: str
    plan: str
    status: str
    industry: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    timezone: Optional[str] = None
    created_at: Optional[str] = None


class PortalSettings(BaseModel):
    greeting: Optional[str] = None
    business_hours: Optional[dict[str, Any]] = None
    notification_email: Optional[str] = None
    notification_sms: Optional[str] = None
    recording_enabled: bool = True
    after_hours_action: str = "voicemail"


class PortalBilling(BaseModel):
    plan: str
    monthly_cost: float
    setup_fee_paid: bool
    next_billing_date: Optional[str] = None
    stripe_portal_url: Optional[str] = None


class OnboardingStatus(BaseModel):
    current_step: int
    total_steps: int
    complete: bool
    steps: list[dict[str, Any]] = []


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_my_account(
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get the current client's account info."""
    tenant = await _get_tenant(db, user.tenant_id)
    return {
        "success": True,
        "data": PortalAccount(
            id=str(tenant.id),
            name=tenant.business_name or tenant.name,
            plan=tenant.plan_tier.value,
            status=tenant.status.value,
            industry=tenant.industry,
            phone=tenant.business_phone,
            email=tenant.business_email,
            timezone=tenant.business_timezone,
            created_at=tenant.created_at.isoformat() if tenant.created_at else None,
        ).model_dump(),
    }


@router.get("/calls")
async def get_my_calls(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get the current client's calls."""
    tenant_id = user.tenant_id
    stmt = select(Call).where(Call.tenant_id == tenant_id)

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            stmt = stmt.where(Call.started_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            stmt = stmt.where(Call.started_at <= dt_to)
        except ValueError:
            pass

    count_stmt = select(func.count(Call.id)).where(Call.tenant_id == tenant_id)
    if date_from:
        try:
            count_stmt = count_stmt.where(Call.started_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            count_stmt = count_stmt.where(Call.started_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    total_result = await db.execute(count_stmt)
    total = total_result.scalar() or 0

    stmt = stmt.order_by(Call.started_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    calls = result.scalars().all()

    return {
        "success": True,
        "data": {
            "calls": [
                {
                    "id": str(c.id),
                    "caller_number": c.caller_number,
                    "direction": c.direction.value if c.direction else None,
                    "status": c.status.value,
                    "result": c.result.value if c.result else None,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "ended_at": c.ended_at.isoformat() if c.ended_at else None,
                    "duration_seconds": c.duration_seconds,
                    "ai_handled": c.ai_handled,
                    "transcript_summary": c.transcript_summary,
                    "intent_detected": c.intent_detected,
                }
                for c in calls
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/calls/{call_id}")
async def get_my_call_detail(
    call_id: str,
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get a single call detail with transcript."""
    try:
        call_uuid = UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid call ID")

    result = await db.execute(
        select(Call).where(Call.id == call_uuid, Call.tenant_id == user.tenant_id)
    )
    call = result.scalar_one_or_none()
    if call is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call not found")

    transcript_result = await db.execute(
        select(Transcript)
        .where(Transcript.call_id == call_uuid)
        .order_by(Transcript.segment_start)
    )
    transcript_rows = transcript_result.scalars().all()

    recording_url = None
    if call.recordings:
        rec = call.recordings[0]
        recording_url = rec.access_url

    return {
        "success": True,
        "data": {
            "call_id": str(call.id),
            "tenant_id": str(call.tenant_id),
            "transcript": [
                {
                    "speaker": t.speaker,
                    "text": t.text,
                    "start": float(t.segment_start),
                    "end": float(t.segment_end),
                    "confidence": float(t.confidence) if t.confidence else None,
                }
                for t in transcript_rows
            ],
            "recording_url": recording_url,
            "duration": call.duration_seconds,
            "status": call.status.value,
            "direction": call.direction.value if call.direction else None,
            "caller_number": call.caller_number,
            "intent": call.intent_detected,
            "summary": call.transcript_summary,
        },
    }


@router.get("/analytics")
async def get_my_analytics(
    days: int = Query(30, ge=1, le=365),
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get the current client's usage analytics."""
    tenant_id = user.tenant_id
    since = datetime.now(timezone.utc) - timedelta(days=days)
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    base_filter = Call.tenant_id == tenant_id

    total_result = await db.execute(
        select(func.count(Call.id)).where(base_filter)
    )
    total_calls = total_result.scalar() or 0

    period_result = await db.execute(
        select(func.count(Call.id)).where(base_filter, Call.started_at >= since)
    )
    period_calls = period_result.scalar() or 0

    month_result = await db.execute(
        select(func.count(Call.id)).where(base_filter, Call.started_at >= month_start)
    )
    month_calls = month_result.scalar() or 0

    answered_result = await db.execute(
        select(func.count(Call.id)).where(
            base_filter,
            Call.started_at >= since,
            Call.status.in_([CallStatus.ANSWERED, CallStatus.ACTIVE, CallStatus.COMPLETED]),
        )
    )
    calls_answered = answered_result.scalar() or 0

    missed_result = await db.execute(
        select(func.count(Call.id)).where(
            base_filter,
            Call.started_at >= since,
            Call.status.in_([CallStatus.NO_ANSWER, CallStatus.FAILED, CallStatus.VOICEMAIL]),
        )
    )
    calls_missed = missed_result.scalar() or 0

    avg_duration_result = await db.execute(
        select(func.avg(Call.duration_seconds)).where(
            base_filter,
            Call.started_at >= since,
            Call.duration_seconds.isnot(None),
        )
    )
    avg_duration = avg_duration_result.scalar()

    avg_answer_result = await db.execute(
        select(func.avg(Call.talk_time_seconds)).where(
            base_filter,
            Call.started_at >= since,
            Call.talk_time_seconds > 0,
        )
    )
    avg_answer_time = avg_answer_result.scalar()

    booking_result = await db.execute(
        select(func.count(Appointment.id)).where(
            Appointment.tenant_id == tenant_id,
            Appointment.created_at >= since,
        )
    )
    bookings_made = booking_result.scalar() or 0

    calls_by_hour_result = await db.execute(
        select(
            func.extract("hour", Call.started_at).label("hour"),
            func.count(Call.id),
        )
        .where(base_filter, Call.started_at >= since)
        .group_by("hour")
        .order_by("hour")
    )
    calls_by_hour = {str(int(row[0])): row[1] for row in calls_by_hour_result.all()}

    calls_by_day_result = await db.execute(
        select(
            cast(Call.started_at, Date).label("day"),
            func.count(Call.id),
        )
        .where(base_filter, Call.started_at >= since)
        .group_by("day")
        .order_by("day")
    )
    calls_by_day = {str(row[0]): row[1] for row in calls_by_day_result.all()}

    intent_result = await db.execute(
        select(Call.intent_detected, func.count(Call.id))
        .where(
            base_filter,
            Call.started_at >= since,
            Call.intent_detected.isnot(None),
        )
        .group_by(Call.intent_detected)
        .order_by(func.count(Call.id).desc())
        .limit(10)
    )
    top_intents = [
        {"intent": row[0], "count": row[1]}
        for row in intent_result.all()
    ]

    return {
        "success": True,
        "data": {
            "tenant_id": str(tenant_id),
            "period_days": days,
            "total_calls": total_calls,
            "calls_this_month": month_calls,
            "calls_answered": calls_answered,
            "calls_missed": calls_missed,
            "avg_duration_seconds": round(float(avg_duration), 1) if avg_duration else None,
            "avg_answer_time": round(float(avg_answer_time), 1) if avg_answer_time else None,
            "bookings_made": bookings_made,
            "booking_rate": round(bookings_made / period_calls, 3) if period_calls > 0 else None,
            "calls_by_hour": calls_by_hour,
            "calls_by_day": calls_by_day,
            "top_intents": top_intents,
        },
    }


@router.get("/settings")
async def get_my_settings(
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get the current client's configurable settings."""
    tenant = await _get_tenant(db, user.tenant_id)
    cfg = await _get_tenant_config(db, user.tenant_id)

    business_hours = cfg.routing_rules.get("business_hours") if cfg.routing_rules else None
    notification_settings = cfg.notification_settings or {}
    recording_enabled = cfg.ai_settings.get("recording_enabled", True) if cfg.ai_settings else True

    return {
        "success": True,
        "data": PortalSettings(
            greeting=tenant.greeting_message,
            business_hours=business_hours,
            notification_email=notification_settings.get("email"),
            notification_sms=notification_settings.get("sms"),
            recording_enabled=recording_enabled,
            after_hours_action=tenant.after_hours_action,
        ).model_dump(),
    }


@router.put("/settings")
async def update_my_settings(
    greeting: Optional[str] = None,
    notification_email: Optional[str] = None,
    notification_sms: Optional[str] = None,
    recording_enabled: Optional[bool] = None,
    after_hours_action: Optional[str] = None,
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Update limited client settings (greeting, notifications, etc)."""
    tenant = await _get_tenant(db, user.tenant_id)
    cfg = await _get_tenant_config(db, user.tenant_id)
    updated_fields = []

    if greeting is not None:
        tenant.greeting_message = greeting
        updated_fields.append("greeting")
    if after_hours_action is not None:
        tenant.after_hours_action = after_hours_action
        updated_fields.append("after_hours_action")
    if recording_enabled is not None:
        ai_settings = dict(cfg.ai_settings) if cfg.ai_settings else {}
        ai_settings["recording_enabled"] = recording_enabled
        cfg.ai_settings = ai_settings
        updated_fields.append("recording_enabled")
    if notification_email is not None or notification_sms is not None:
        notif = dict(cfg.notification_settings) if cfg.notification_settings else {}
        if notification_email is not None:
            notif["email"] = notification_email
            updated_fields.append("notification_email")
        if notification_sms is not None:
            notif["sms"] = notification_sms
            updated_fields.append("notification_sms")
        cfg.notification_settings = notif

    await db.flush()
    logger.info("portal.settings_updated", tenant_id=str(user.tenant_id), fields=updated_fields)

    return {
        "success": True,
        "data": {
            "message": "Settings updated",
            "updated_fields": updated_fields,
        },
    }


@router.get("/billing")
async def get_my_billing(
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get billing summary and Stripe portal link."""
    tenant = await _get_tenant(db, user.tenant_id)

    plan = tenant.plan_tier
    monthly_cost = PLAN_PRICES.get(plan, 0)
    setup_fee_paid = tenant.status.value in ("active", "limited")

    next_billing_date = None
    if tenant.plan_expires_at:
        next_billing_date = tenant.plan_expires_at.isoformat()

    return {
        "success": True,
        "data": PortalBilling(
            plan=plan.value,
            monthly_cost=monthly_cost,
            setup_fee_paid=setup_fee_paid,
            next_billing_date=next_billing_date,
            stripe_portal_url=None,
        ).model_dump(),
    }


@router.get("/onboarding")
async def get_my_onboarding(
    user=CurrentUser,
    db: AsyncSession = DBSession,
) -> dict[str, Any]:
    """Get the client's onboarding checklist status."""
    tenant = await _get_tenant(db, user.tenant_id)

    has_business_info = bool(
        tenant.business_phone or tenant.business_email or tenant.industry
    )

    has_phone = bool(tenant.business_phone)

    has_calls_result = await db.execute(
        select(func.count(Call.id)).where(Call.tenant_id == tenant.id)
    )
    has_calls = (has_calls_result.scalar() or 0) > 0

    has_faq_result = await db.execute(
        select(func.count(FAQEntry.id)).where(FAQEntry.tenant_id == tenant.id)
    )
    has_faq = (has_faq_result.scalar() or 0) > 0

    has_hours_result = await db.execute(
        select(func.count(BusinessHours.id)).where(BusinessHours.tenant_id == tenant.id)
    )
    has_hours = (has_hours_result.scalar() or 0) > 0

    has_test_calls = has_calls

    has_live_calls_result = await db.execute(
        select(func.count(Call.id)).where(
            Call.tenant_id == tenant.id,
            Call.status == CallStatus.COMPLETED,
        )
    )
    has_live_calls = (has_live_calls_result.scalar() or 0) > 0

    step_checks = [
        True,
        has_business_info and has_faq and has_hours,
        True,
        has_phone,
        has_test_calls,
        has_live_calls,
    ]

    steps = []
    for i, (step_def, completed) in enumerate(zip(ONBOARDING_STEPS, step_checks), start=1):
        steps.append({
            "step": i,
            "name": step_def["name"],
            "description": step_def["description"],
            "completed": completed,
        })

    completed_count = sum(1 for s in steps if s["completed"])

    return {
        "success": True,
        "data": OnboardingStatus(
            current_step=completed_count,
            total_steps=len(steps),
            complete=completed_count >= len(steps),
            steps=steps,
        ).model_dump(),
    }

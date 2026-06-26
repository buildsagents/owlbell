"""api/routes/agent_tools.py - Retell AI custom tool endpoints.

Called by Retell during a live call when the LLM invokes a custom function.
Each endpoint receives the Retell tool call payload, authenticates via shared
secret, performs the action, and returns a result the LLM can use.

Endpoints (mounted at /api/v1/agent/tools):
    POST /lookup-caller    — find existing caller profile by phone
    POST /log-message      — save a caller's message for the business
    POST /qualify-lead     — score and log a lead
    POST /check-availability — search open time slots
    POST /book-appointment  — create an appointment
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time, timedelta
from typing import Any, AsyncGenerator, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from backend.config import get_settings
from backend.db.models.business import Appointment, CallerProfile
from backend.db.models.enums import AppointmentStatus
from backend.db.models.tenant import Tenant

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/agent/tools", tags=["Agent Tools"])


# ---------------------------------------------------------------------------
# DB session helper
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _get_session() -> AsyncGenerator[Any, None]:
    from backend.dependencies import get_session_maker

    sm = get_session_maker()
    if sm is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database not initialized")
    session = sm()
    try:
        yield session
        await session.commit()
    except HTTPException:
        await session.rollback()
        raise
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _verify_auth(request: Request) -> None:
    """Check the shared secret in the Authorization header."""
    settings = get_settings()
    secret = settings.integrations.retell_agent_tools_secret
    if secret:
        auth = request.headers.get("Authorization", "")
        expected = f"Bearer {secret.get_secret_value()}"
        if auth != expected:
            raise HTTPException(status_code=401, detail="Invalid auth")


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------


async def _resolve_tenant(payload: dict) -> tuple[Any, str]:
    """Resolve tenant from the Retell call payload.

    Looks up the business by the `to_number` in the call object.
    Returns (tenant, tenant_id_str).
    """
    call_obj = payload.get("call", {}) or {}
    to_number = call_obj.get("to_number", "")
    if to_number:
        async with _get_session() as db:
            result = await db.execute(
                select(Tenant).where(Tenant.business_phone == to_number, Tenant.status == "ACTIVE")
            )
            tenant = result.scalar_one_or_none()
            if tenant:
                return tenant, str(tenant.id)

    return None, "unknown"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_phone(raw: str) -> str:
    digits = "".join(c for c in raw if c.isdigit() or c == "+")
    return digits if digits.startswith("+") else f"+1{digits}" if digits else ""


def _phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _parse_date(val: str) -> date:
    try:
        return date.fromisoformat(val)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid date: {val}")


def _parse_time(val: str) -> time:
    try:
        return time.fromisoformat(val)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"Invalid time: {val}")


# ---------------------------------------------------------------------------
# 1. Lookup Caller
# ---------------------------------------------------------------------------


@router.post("/lookup-caller")
async def lookup_caller(request: Request, payload: dict) -> dict:
    _verify_auth(request)
    args = payload.get("args", payload) if payload.get("args_at_root") else payload.get("args", {})
    phone = args.get("phone_number", "")
    normalized = _normalize_phone(phone)
    if not normalized:
        return {"found": False, "error": "No valid phone number provided"}

    tenant, _ = await _resolve_tenant(payload)
    if not tenant:
        return {"found": False, "error": "No matching tenant"}

    phash = _phone_hash(normalized)
    async with _get_session() as db:
        result = await db.execute(
            select(CallerProfile).where(
                CallerProfile.tenant_id == tenant.id,
                CallerProfile.phone_hash == phash,
            )
        )
        profile = result.scalar_one_or_none()

    if profile:
        return {
            "found": True,
            "caller_name": profile.name or "",
            "email": profile.email or "",
            "notes": profile.notes or "",
            "priority": profile.priority,
            "total_calls": profile.total_calls,
            "preferred_language": profile.preferred_language,
        }

    return {"found": False}


# ---------------------------------------------------------------------------
# 2. Log Message
# ---------------------------------------------------------------------------


@router.post("/log-message")
async def log_message(request: Request, payload: dict) -> dict:
    _verify_auth(request)
    args = payload.get("args", payload) if payload.get("args_at_root") else payload.get("args", {})
    caller_name = (args.get("caller_name") or "").strip()
    caller_phone = _normalize_phone(args.get("caller_phone") or "")
    message_text = (args.get("message") or "").strip()
    email = (args.get("email") or "").strip()

    if not caller_phone and not caller_name:
        return {"success": False, "error": "Need at least a name or phone number"}
    if not message_text:
        return {"success": False, "error": "Message text is required"}

    tenant, tenant_id = await _resolve_tenant(payload)

    async with _get_session() as db:
        msg_id = str(uuid.uuid4())
        if not caller_name:
            caller_name = "Unknown"

        # Update / create CallerProfile with the message
        if caller_phone and tenant:
            phash = _phone_hash(caller_phone)
            existing = (
                await db.execute(
                    select(CallerProfile).where(
                        CallerProfile.tenant_id == tenant.id,
                        CallerProfile.phone_hash == phash,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                existing.total_calls += 1
                existing.last_call_at = datetime.utcnow()
                existing.notes = f"Left message: {message_text[:300]}"
            else:
                profile = CallerProfile(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    phone_number=caller_phone,
                    phone_hash=phash,
                    name=caller_name,
                    email=email or None,
                    notes=f"Left message: {message_text[:300]}",
                    total_calls=1,
                    last_call_at=datetime.utcnow(),
                )
                db.add(profile)

    logger.info("agent.message_logged", caller_name=caller_name, phone=caller_phone)
    return {"success": True, "message_id": msg_id, "message": "Message logged successfully"}


# ---------------------------------------------------------------------------
# 3. Qualify Lead
# ---------------------------------------------------------------------------


@router.post("/qualify-lead")
async def qualify_lead(request: Request, payload: dict) -> dict:
    _verify_auth(request)
    args = payload.get("args", payload) if payload.get("args_at_root") else payload.get("args", {})

    caller_name = (args.get("caller_name") or "").strip()
    caller_phone = _normalize_phone(args.get("caller_phone") or "")
    service = (args.get("service") or "").strip()
    urgency = (args.get("urgency") or "flexible").strip().lower()
    address = (args.get("address") or "").strip()
    notes = (args.get("notes") or "").strip()

    tenant, tenant_id = await _resolve_tenant(payload)

    # Simple lead scoring
    score_map = {"emergency": 0.9, "asap": 0.75, "flexible": 0.4}
    urgency_score = score_map.get(urgency, 0.4)
    has_name = 0.1 if caller_name else 0
    has_phone = 0.1 if caller_phone else 0
    has_service = 0.15 if service else 0
    has_address = 0.1 if address else 0
    score = round(min(urgency_score + has_name + has_phone + has_service + has_address, 1.0), 2)

    async with _get_session() as db:
        lead_id = str(uuid.uuid4())

        # Store lead info in CallerProfile
        if caller_phone and tenant:
            phash = _phone_hash(caller_phone)
            existing = (
                await db.execute(
                    select(CallerProfile).where(
                        CallerProfile.tenant_id == tenant.id,
                        CallerProfile.phone_hash == phash,
                    )
                )
            ).scalar_one_or_none()

            tags = []
            if existing:
                existing.total_calls += 1
                existing.last_call_at = datetime.utcnow()
                existing.notes = (
                    f"Lead: {service} ({urgency}), score={score}. {notes}"
                )
                tags = list(existing.tags_json or [])
            else:
                profile = CallerProfile(
                    id=uuid.uuid4(),
                    tenant_id=tenant.id,
                    phone_number=caller_phone,
                    phone_hash=phash,
                    name=caller_name or None,
                    notes=f"Lead: {service} ({urgency}), score={score}. {notes}"[:500],
                    total_calls=1,
                    last_call_at=datetime.utcnow(),
                )
                db.add(profile)

            if "lead" not in tags:
                tags.append("lead")
            if urgency not in tags:
                tags.append(urgency)

            if existing:
                existing.tags_json = tags
            else:
                pass  # new profile has no tags_json set yet

    logger.info("agent.lead_qualified", name=caller_name, service=service, score=score)
    return {
        "success": True,
        "lead_id": lead_id,
        "score": score,
        "urgency": urgency,
        "service": service,
        "message": f"Lead qualified with score {score}",
    }


# ---------------------------------------------------------------------------
# 4. Check Availability
# ---------------------------------------------------------------------------


@router.post("/check-availability")
async def check_availability(request: Request, payload: dict) -> dict:
    _verify_auth(request)
    args = payload.get("args", payload) if payload.get("args_at_root") else payload.get("args", {})

    raw_date = args.get("date", "")
    check_date = _parse_date(raw_date) if raw_date else date.today()

    tenant, tenant_id = await _resolve_tenant(payload)
    if not tenant:
        return {"available": False, "error": "Tenant not found"}

    tid = uuid.UUID(tenant_id)
    async with _get_session() as db:
        existing = await db.execute(
            select(Appointment).where(
                Appointment.tenant_id == tid,
                Appointment.scheduled_date == check_date,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            )
        )
        booked = existing.scalars().all()

    # Build slot map: 30-min slots from 8 AM to 6 PM
    all_slots = []
    for hour in range(8, 18):
        for minute in (0, 30):
            slot_start = time(hour, minute)
            slot_end = (time(hour, minute + 30) if minute == 0 else time(hour + 1, 0))
            if slot_end.hour > 18:
                continue

            conflict = any(
                b.start_time <= slot_start < b.end_time or
                b.start_time < slot_end <= b.end_time or
                (slot_start <= b.start_time and slot_end >= b.end_time)
                for b in booked
            )
            if not conflict:
                all_slots.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                })

    return {
        "available": len(all_slots) > 0,
        "date": check_date.isoformat(),
        "slots": all_slots[:10],
    }


# ---------------------------------------------------------------------------
# 5. Book Appointment
# ---------------------------------------------------------------------------

DURATIONS = {
    "hvac": 120,
    "plumbing": 90,
    "electrical": 90,
    "roofing": 180,
    "general": 60,
}


@router.post("/book-appointment")
async def book_appointment(request: Request, payload: dict) -> dict:
    _verify_auth(request)
    args = payload.get("args", payload) if payload.get("args_at_root") else payload.get("args", {})

    caller_name = (args.get("caller_name") or "").strip()
    caller_phone = _normalize_phone(args.get("caller_phone") or "")
    service = (args.get("service") or "general").strip().lower()
    appointment_date = _parse_date(args.get("date") or "")
    appointment_time = _parse_time(args.get("time") or "09:00")
    address = (args.get("address") or "").strip()
    notes = (args.get("notes") or "").strip()

    if not caller_phone:
        return {"success": False, "error": "Phone number required"}
    if not caller_name:
        return {"success": False, "error": "Caller name required"}

    tenant, tenant_id = await _resolve_tenant(payload)
    if not tenant:
        return {"success": False, "error": "Tenant not found"}

    duration_min = DURATIONS.get(service, 60)
    start_dt = datetime.combine(appointment_date, appointment_time)
    end_dt = start_dt + timedelta(minutes=duration_min)

    # Validate not in past
    now = datetime.utcnow()
    if start_dt < now:
        return {"success": False, "error": "Cannot book in the past"}

    tid = uuid.UUID(tenant_id)
    async with _get_session() as db:
        # Check conflict
        existing = await db.execute(
            select(Appointment).where(
                Appointment.tenant_id == tid,
                Appointment.scheduled_date == appointment_date,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            )
        )
        for booked in existing.scalars().all():
            if booked.start_time <= appointment_time < booked.end_time:
                return {
                    "success": False,
                    "error": f"That slot conflicts with another appointment ({booked.caller_name})",
                }

        appt = Appointment(
            id=uuid.uuid4(),
            tenant_id=tid,
            caller_number=caller_phone,
            caller_name=caller_name,
            title=f"{service.title()} - {caller_name}",
            description=notes or f"{service.title()} appointment",
            scheduled_date=appointment_date,
            start_time=appointment_time,
            end_time=end_dt.time(),
            appointment_type="in_person",
            location=address or None,
        )
        db.add(appt)

        # Update caller profile
        phash = _phone_hash(caller_phone)
        existing_profile = (
            await db.execute(
                select(CallerProfile).where(
                    CallerProfile.tenant_id == tid,
                    CallerProfile.phone_hash == phash,
                )
            )
        ).scalar_one_or_none()
        if existing_profile:
            existing_profile.total_calls += 1
            existing_profile.last_call_at = datetime.utcnow()
            tags = list(existing_profile.tags_json or [])
            if "appointment_booked" not in tags:
                tags.append("appointment_booked")
            existing_profile.tags_json = tags
        else:
            profile = CallerProfile(
                id=uuid.uuid4(),
                tenant_id=tid,
                phone_number=caller_phone,
                phone_hash=phash,
                name=caller_name,
                notes=f"Booked {service} on {appointment_date} at {appointment_time}",
                tags_json=["appointment_booked"],
                total_calls=1,
                last_call_at=datetime.utcnow(),
            )
            db.add(profile)

        logger.info(
            "agent.appointment_booked",
            name=caller_name,
            date=str(appointment_date),
            time=str(appointment_time),
        )

        return {
            "success": True,
            "appointment_id": str(appt.id),
            "date": appointment_date.isoformat(),
            "time": appointment_time.isoformat(),
            "service": service,
            "message": f"Appointment booked for {caller_name} on {appointment_date} at {appointment_time}",
        }

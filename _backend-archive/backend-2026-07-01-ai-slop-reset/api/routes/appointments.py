"""api/routes/appointments.py - Appointment scheduling routes (10 endpoints).

Provides appointment CRUD, availability checking, business hours management.
All operations use the database via AppointmentService and direct queries.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, DBSession
from api.schemas.appointments import (
    AppointmentCancelRequest,
    AppointmentContact,
    AppointmentCreateRequest,
    AppointmentListParams,
    AppointmentListResponse,
    AppointmentRecord,
    AppointmentService as AppointmentServiceSchema,
    AppointmentStatsResponse,
    AppointmentUpdateRequest,
    AvailabilityQueryParams,
    AvailabilityResponse,
    BusinessHoursConfig,
    BusinessHoursEntry,
    BusinessHoursUpdateRequest,
    DailyAvailability,
    TimeSlot,
)
from api.schemas.base import AppointmentStatus, DayOfWeek, ResponseMeta, SuccessResponse
from backend.business.appointments.service import AppointmentService
from backend.db.models.business import Appointment, BusinessHours
from backend.db.models.enums import AppointmentStatus as DBAppointmentStatus

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/appointments", tags=["Appointments"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _appointment_to_record(appt: Appointment) -> AppointmentRecord:
    """Convert an Appointment ORM model to the API AppointmentRecord schema."""
    meta = appt.metadata_json or {}

    contact = AppointmentContact(
        name=appt.caller_name or "Unknown",
        phone=appt.caller_number or "",
        email=meta.get("contact_email"),
    )

    service = AppointmentServiceSchema(
        name=meta.get("service_name", appt.title or "Appointment"),
        duration_minutes=meta.get("service_duration_minutes", 30),
        price=meta.get("service_price"),
        description=meta.get("service_description"),
    )

    return AppointmentRecord(
        id=appt.id,
        tenant_id=appt.tenant_id,
        call_id=appt.call_id,
        status=AppointmentStatus(appt.status.value) if appt.status else AppointmentStatus.PENDING,
        contact=contact,
        service=service,
        appointment_date=appt.scheduled_date,
        start_time=appt.start_time,
        end_time=appt.end_time,
        timezone=appt.timezone,
        notes=appt.description,
        ai_transcript_excerpt=meta.get("ai_transcript_excerpt"),
        reminder_sent=appt.reminder_sent_at is not None,
        cancelled_reason=appt.cancellation_reason,
        created_at=appt.created_at,
        updated_at=appt.updated_at,
    )


async def _load_business_hours_config(
    db: AsyncSession, tenant_id: uuid.UUID
) -> tuple[list[BusinessHours], dict[str, Any]]:
    """Load BusinessHours rows and tenant config for a tenant."""
    result = await db.execute(
        select(BusinessHours).where(
            BusinessHours.tenant_id == tenant_id,
            BusinessHours.is_override == False,
        )
    )
    hours_rows = list(result.scalars().all())

    tenant_result = await db.execute(
        select(func.count()).select_from(BusinessHours).where(BusinessHours.tenant_id == tenant_id)
    )
    return hours_rows, {}


def _build_hours_config(hours_rows: list[BusinessHours]) -> BusinessHoursConfig:
    """Build BusinessHoursConfig schema from ORM rows."""
    day_order = DayOfWeek.__members__.values()
    hours_by_day: dict[str, BusinessHours] = {}
    for h in hours_rows:
        if h.day_of_week not in hours_by_day:
            hours_by_day[h.day_of_week] = h

    hours_entries: list[BusinessHoursEntry] = []
    for day in day_order:
        bh = hours_by_day.get(day.value)
        if bh and not bh.is_closed:
            entry = BusinessHoursEntry(
                day=day,
                is_open=True,
                open_time=bh.open_time,
                close_time=bh.close_time,
                breaks=[],
            )
        else:
            entry = BusinessHoursEntry(day=day, is_open=False, breaks=[])
        hours_entries.append(entry)

    timezone = hours_rows[0].timezone if hours_rows else "America/New_York"

    return BusinessHoursConfig(
        timezone=timezone,
        hours=hours_entries,
        holidays=[],
        appointment_interval_minutes=30,
        buffer_minutes_between=0,
        max_future_booking_days=90,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[AppointmentListResponse],
    summary="List appointments",
    description="List appointments with pagination and filtering.",
)
async def list_appointments(
    params: AppointmentListParams = Depends(),
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentListResponse]:
    """List appointments with pagination and filtering."""
    svc = AppointmentService(db, tenant.id)

    filters: dict[str, Any] = {}
    if params.status:
        filters["status"] = DBAppointmentStatus(params.status.value)
    if params.contact_phone:
        filters["caller_number"] = params.contact_phone
    if params.start_date:
        filters["date_from"] = params.start_date
    if params.end_date:
        filters["date_to"] = params.end_date
    if params.upcoming_only:
        filters["date_from"] = date.today()
    if params.search:
        filters["search"] = params.search

    items, total = await svc.list_appointments(
        filters=filters or None,
        limit=params.per_page,
        offset=(params.page - 1) * params.per_page,
    )

    records = [_appointment_to_record(a) for a in items]

    return SuccessResponse(
        data=AppointmentListResponse(items=records, total=total),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/stats",
    response_model=SuccessResponse[AppointmentStatsResponse],
    summary="Appointment stats",
    description="Get appointment statistics.",
)
async def get_appointment_stats(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentStatsResponse]:
    """Get appointment statistics."""
    svc = AppointmentService(db, tenant.id)

    stats = await svc.get_appointment_stats()

    total = sum(row["count"] for row in stats)
    by_status: dict[str, int] = {}
    for row in stats:
        by_status[row["status"].value if hasattr(row["status"], "value") else str(row["status"])] = row["count"]

    today = date.today()
    count_result = await db.execute(
        select(func.count()).select_from(Appointment).where(
            Appointment.tenant_id == tenant.id,
            Appointment.scheduled_date >= today,
            Appointment.status.notin_([DBAppointmentStatus.CANCELLED]),
        )
    )
    upcoming = count_result.scalar_one()

    now = datetime.utcnow()
    period_start = now - timedelta(days=30)

    return SuccessResponse(
        data=AppointmentStatsResponse(
            total_appointments=total,
            upcoming_count=upcoming,
            by_status=by_status,
            period_start=period_start,
            period_end=now,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "",
    response_model=SuccessResponse[AppointmentRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Create appointment",
    description="Create a new appointment.",
)
async def create_appointment(
    body: AppointmentCreateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentRecord]:
    """Create a new appointment."""
    tz = body.timezone or getattr(tenant, "timezone", "America/New_York")

    metadata: dict[str, Any] = {}
    if body.contact.email:
        metadata["contact_email"] = body.contact.email
    metadata["service_name"] = body.service.name
    metadata["service_duration_minutes"] = body.service.duration_minutes
    if body.service.price:
        metadata["service_price"] = body.service.price
    if body.service.description:
        metadata["service_description"] = body.service.description

    appt_data: dict[str, Any] = {
        "tenant_id": tenant.id,
        "call_id": body.call_id,
        "caller_name": body.contact.name,
        "caller_number": body.contact.phone,
        "title": body.service.name,
        "description": body.notes,
        "status": DBAppointmentStatus.CONFIRMED,
        "scheduled_date": body.appointment_date,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "timezone": tz,
        "appointment_type": "in_person",
        "metadata_json": metadata,
    }

    svc = AppointmentService(db, tenant.id)
    appt = await svc.create_appointment(appt_data)
    await db.refresh(appt)

    logger.info("appointment.created", appointment_id=str(appt.id))

    return SuccessResponse(
        data=_appointment_to_record(appt),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/{appointment_id}",
    response_model=SuccessResponse[AppointmentRecord],
    summary="Get appointment",
    description="Get a single appointment by ID.",
)
async def get_appointment(
    appointment_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentRecord]:
    """Get appointment detail."""
    svc = AppointmentService(db, tenant.id)
    try:
        appt = await svc.get_appointment(appointment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Appointment not found")

    return SuccessResponse(
        data=_appointment_to_record(appt),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/{appointment_id}",
    response_model=SuccessResponse[AppointmentRecord],
    summary="Update appointment",
    description="Update appointment details.",
)
async def update_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentRecord]:
    """Update appointment details."""
    svc = AppointmentService(db, tenant.id)
    try:
        appt = await svc.get_appointment(appointment_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Appointment not found")

    update_data: dict[str, Any] = {}
    if body.status is not None:
        update_data["status"] = DBAppointmentStatus(body.status.value)
    if body.appointment_date is not None:
        update_data["scheduled_date"] = body.appointment_date
    if body.start_time is not None:
        update_data["start_time"] = body.start_time
    if body.end_time is not None:
        update_data["end_time"] = body.end_time
    if body.notes is not None:
        update_data["description"] = body.notes

    if update_data:
        appt = await svc.update_appointment(appointment_id, update_data)
        await db.refresh(appt)

    return SuccessResponse(
        data=_appointment_to_record(appt),
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{appointment_id}/cancel",
    response_model=SuccessResponse[AppointmentRecord],
    summary="Cancel appointment",
    description="Cancel an appointment with optional reason.",
)
async def cancel_appointment(
    appointment_id: uuid.UUID,
    body: AppointmentCancelRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AppointmentRecord]:
    """Cancel an appointment."""
    svc = AppointmentService(db, tenant.id)
    try:
        appt = await svc.cancel_appointment(appointment_id, body.reason or "No reason provided")
        await db.refresh(appt)
    except ValueError:
        raise HTTPException(status_code=404, detail="Appointment not found")

    logger.info(
        "appointment.cancelled",
        appointment_id=str(appointment_id),
        reason=body.reason,
    )

    return SuccessResponse(
        data=_appointment_to_record(appt),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/availability/slots",
    response_model=SuccessResponse[AvailabilityResponse],
    summary="Check availability",
    description="Get available appointment slots for a date range.",
)
async def get_availability(
    params: AvailabilityQueryParams = Depends(),
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[AvailabilityResponse]:
    """Check availability for a date range."""
    svc = AppointmentService(db, tenant.id)
    available_slots = await svc.check_availability(
        params.start_date,
        params.end_date,
        params.service_duration,
    )

    available_map: dict[str, set[tuple[str, str]]] = {}
    for slot in available_slots:
        d = slot["date"]
        available_map.setdefault(d, set()).add((slot["start_time"], slot["end_time"]))

    hours_rows, _ = await _load_business_hours_config(db, tenant.id)
    hours_by_day: dict[str, BusinessHours] = {}
    for h in hours_rows:
        if h.day_of_week not in hours_by_day:
            hours_by_day[h.day_of_week] = h

    days: list[DailyAvailability] = []
    current = params.start_date
    while current <= params.end_date:
        day_name = current.strftime("%A").lower()
        day_hours = hours_by_day.get(day_name)

        slots_for_date: list[TimeSlot] = []
        is_open = False

        if day_hours and not day_hours.is_closed:
            is_open = True
            slot_start = datetime.combine(current, day_hours.open_time)
            slot_end_bound = datetime.combine(current, day_hours.close_time)
            interval = timedelta(minutes=30)
            duration = timedelta(minutes=params.service_duration)

            available_for_date = available_map.get(current.isoformat(), set())

            current_dt = slot_start
            while current_dt + duration <= slot_end_bound:
                slot_end_dt = current_dt + duration
                key = (current_dt.time().isoformat(), slot_end_dt.time().isoformat())
                is_available = key in available_for_date

                slots_for_date.append(TimeSlot(
                    start_time=current_dt.time(),
                    end_time=slot_end_dt.time(),
                    is_available=is_available,
                ))
                current_dt += interval

        days.append(DailyAvailability(
            date=current,
            day_of_week=day_name,
            slots=slots_for_date,
            is_fully_booked=is_open and all(not s.is_available for s in slots_for_date),
            is_business_closed=not is_open,
        ))
        current += timedelta(days=1)

    timezone = hours_rows[0].timezone if hours_rows else "America/New_York"

    return SuccessResponse(
        data=AvailabilityResponse(
            days=days,
            timezone=timezone,
            service_duration=params.service_duration,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/business-hours/config",
    response_model=SuccessResponse[BusinessHoursConfig],
    summary="Get business hours",
    description="Get business hours configuration.",
)
async def get_business_hours(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[BusinessHoursConfig]:
    """Get business hours config."""
    hours_rows, _ = await _load_business_hours_config(db, tenant.id)
    config = _build_hours_config(hours_rows)

    return SuccessResponse(
        data=config,
        meta=ResponseMeta(request_id=""),
    )


@router.put(
    "/business-hours/config",
    response_model=SuccessResponse[BusinessHoursConfig],
    summary="Update business hours",
    description="Update business hours configuration.",
)
async def update_business_hours(
    body: BusinessHoursUpdateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[BusinessHoursConfig]:
    """Update business hours configuration."""
    tz = body.timezone or "America/New_York"

    existing_result = await db.execute(
        select(BusinessHours).where(
            BusinessHours.tenant_id == tenant.id,
            BusinessHours.is_override == False,
        )
    )
    existing_rows = existing_result.scalars().all()
    existing_map: dict[str, BusinessHours] = {h.day_of_week: h for h in existing_rows}

    updated_days: set[str] = set()
    if body.hours is not None:
        for entry in body.hours:
            day_str = entry.day.value
            is_closed = not entry.is_open
            open_time = entry.open_time or time(9, 0)
            close_time = entry.close_time or time(17, 0)

            if day_str in existing_map:
                bh = existing_map[day_str]
                bh.is_closed = is_closed
                bh.open_time = open_time
                bh.close_time = close_time
                bh.timezone = tz
            else:
                new_bh = BusinessHours(
                    tenant_id=tenant.id,
                    day_of_week=day_str,
                    open_time=open_time,
                    close_time=close_time,
                    is_closed=is_closed,
                    timezone=tz,
                    is_override=False,
                )
                db.add(new_bh)

            updated_days.add(day_str)

    await db.flush()

    logger.info("business_hours.updated", tenant_id=str(tenant.id))

    # Reload and return
    hours_rows, _ = await _load_business_hours_config(db, tenant.id)
    config = _build_hours_config(hours_rows)

    return SuccessResponse(
        data=config,
        meta=ResponseMeta(request_id=""),
    )

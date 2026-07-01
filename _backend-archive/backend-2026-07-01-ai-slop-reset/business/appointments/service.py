from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any, Optional, Sequence
from uuid import UUID

import structlog
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.business import Appointment, BusinessHours, HolidaySchedule
from backend.db.models.enums import AppointmentStatus
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)


class AppointmentService:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self._session = session
        self._tenant_id = tenant_id
        self._repo = TenantScopedRepository(session, Appointment, tenant_id)
        self._hours_repo = TenantScopedRepository(session, BusinessHours, tenant_id)

    async def create_appointment(self, data: dict[str, Any]) -> Appointment:
        appointment = await self._repo.create(**data)
        logger.info(
            "appointment.created",
            appointment_id=str(appointment.id),
            tenant_id=str(self._tenant_id),
        )
        return appointment

    async def get_appointment(self, appointment_id: UUID) -> Appointment:
        appointment = await self._repo.get_by_id(appointment_id)
        if appointment is None:
            raise ValueError(f"Appointment {appointment_id} not found")
        return appointment

    async def list_appointments(
        self,
        filters: Optional[dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Appointment], int]:
        query = select(Appointment).where(Appointment.tenant_id == self._tenant_id)
        count_query = select(func.count()).select_from(Appointment).where(Appointment.tenant_id == self._tenant_id)

        if filters:
            if filters.get("status"):
                query = query.where(Appointment.status == filters["status"])
                count_query = count_query.where(Appointment.status == filters["status"])
            if filters.get("date_from"):
                query = query.where(Appointment.scheduled_date >= filters["date_from"])
                count_query = count_query.where(Appointment.scheduled_date >= filters["date_from"])
            if filters.get("date_to"):
                query = query.where(Appointment.scheduled_date <= filters["date_to"])
                count_query = count_query.where(Appointment.scheduled_date <= filters["date_to"])
            if filters.get("caller_number"):
                query = query.where(Appointment.caller_number == filters["caller_number"])
                count_query = count_query.where(Appointment.caller_number == filters["caller_number"])
            if filters.get("search"):
                pattern = f"%{filters['search']}%"
                query = query.where(
                    or_(
                        Appointment.caller_name.ilike(pattern),
                        Appointment.title.ilike(pattern),
                    )
                )
                count_query = count_query.where(
                    or_(
                        Appointment.caller_name.ilike(pattern),
                        Appointment.title.ilike(pattern),
                    )
                )

        query = query.order_by(Appointment.scheduled_date.desc(), Appointment.start_time.desc())
        query = query.limit(limit).offset(offset)

        result = await self._session.execute(query)
        items = result.scalars().all()

        count_result = await self._session.execute(count_query)
        total = count_result.scalar_one()

        return items, total

    async def update_appointment(self, appointment_id: UUID, data: dict[str, Any]) -> Appointment:
        appointment = await self._repo.update(appointment_id, **data)
        if appointment is None:
            raise ValueError(f"Appointment {appointment_id} not found")
        # Stamp completion time so the review-request automation has an anchor.
        if (
            appointment.status == AppointmentStatus.COMPLETED
            and appointment.completed_at is None
        ):
            appointment.completed_at = datetime.utcnow()
            await self._session.flush()
        logger.info(
            "appointment.updated",
            appointment_id=str(appointment_id),
            tenant_id=str(self._tenant_id),
        )
        return appointment

    async def cancel_appointment(self, appointment_id: UUID, reason: str) -> Appointment:
        appointment = await self.get_appointment(appointment_id)
        appointment.status = AppointmentStatus.CANCELLED
        appointment.cancelled_at = datetime.utcnow()
        appointment.cancellation_reason = reason
        await self._session.flush()
        logger.info(
            "appointment.cancelled",
            appointment_id=str(appointment_id),
            reason=reason,
            tenant_id=str(self._tenant_id),
        )
        return appointment

    async def get_appointment_stats(self) -> list[dict[str, Any]]:
        query = select(
            Appointment.status,
            func.count().label("count"),
        ).where(
            Appointment.tenant_id == self._tenant_id
        ).group_by(Appointment.status)

        result = await self._session.execute(query)
        rows = result.all()
        return [{"status": row.status, "count": row.count} for row in rows]

    async def check_availability(
        self,
        start_date: date,
        end_date: date,
        service_duration: int,
    ) -> list[dict[str, Any]]:
        hours_query = select(BusinessHours).where(
            BusinessHours.tenant_id == self._tenant_id,
            BusinessHours.is_closed == False,
            or_(
                BusinessHours.effective_to.is_(None),
                BusinessHours.effective_to >= start_date,
            ),
        )
        hours_result = await self._session.execute(hours_query)
        business_hours = hours_result.scalars().all()

        holidays_query = select(HolidaySchedule).where(
            HolidaySchedule.tenant_id == self._tenant_id,
            HolidaySchedule.date.between(start_date, end_date),
        )
        holidays_result = await self._session.execute(holidays_query)
        holidays = holidays_result.scalars().all()

        holiday_dates = {h.date for h in holidays if h.is_closed}

        appointments_query = select(Appointment).where(
            Appointment.tenant_id == self._tenant_id,
            Appointment.scheduled_date.between(start_date, end_date),
            Appointment.status.notin_([AppointmentStatus.CANCELLED]),
        )
        appointments_result = await self._session.execute(appointments_query)
        existing = appointments_result.scalars().all()

        hours_by_day: dict[str, list[BusinessHours]] = {}
        for h in business_hours:
            hours_by_day.setdefault(h.day_of_week, []).append(h)

        slots: list[dict[str, Any]] = []
        current_date = start_date
        while current_date <= end_date:
            if current_date in holiday_dates:
                current_date += timedelta(days=1)
                continue

            day_name = current_date.strftime("%A").lower()
            day_hours = hours_by_day.get(day_name, [])
            if not day_hours:
                current_date += timedelta(days=1)
                continue

            day_appointments = [a for a in existing if a.scheduled_date == current_date]

            for bh in day_hours:
            # Use datetime.combine with current_date for proper comparison
                slot_start = datetime.combine(current_date, bh.open_time)
                slot_end = datetime.combine(current_date, bh.close_time)
                slot_duration = timedelta(minutes=service_duration)

                current_slot = slot_start
                while current_slot + slot_duration <= slot_end:
                    slot_end_time = current_slot + slot_duration
                    conflict = False
                    for apt in day_appointments:
                        apt_start = datetime.combine(current_date, apt.start_time)
                        apt_end = datetime.combine(current_date, apt.end_time)
                        if current_slot < apt_end and slot_end_time > apt_start:
                            conflict = True
                            break
                    if not conflict:
                        slots.append({
                            "date": current_date.isoformat(),
                            "start_time": current_slot.time().isoformat(),
                            "end_time": slot_end_time.time().isoformat(),
                        })
                    current_slot += timedelta(minutes=30)

            current_date += timedelta(days=1)

        return slots

    async def get_business_hours(self) -> Sequence[BusinessHours]:
        return await self._hours_repo.get_all(order_by=BusinessHours.day_of_week)

    async def update_business_hours(self, data: list[dict[str, Any]]) -> list[BusinessHours]:
        existing = await self._hours_repo.get_all()
        existing_map = {e.day_of_week: e for e in existing}

        updated: list[BusinessHours] = []
        for entry in data:
            day = entry.get("day_of_week")
            if day in existing_map:
                obj = existing_map[day]
                for key, value in entry.items():
                    if key != "day_of_week":
                        setattr(obj, key, value)
                updated.append(obj)
            else:
                obj = await self._hours_repo.create(**entry)
                updated.append(obj)

        await self._session.flush()
        logger.info(
            "business_hours.updated",
            tenant_id=str(self._tenant_id),
            days=[e["day_of_week"] for e in data],
        )
        return updated

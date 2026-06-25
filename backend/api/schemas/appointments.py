"""api/schemas/appointments.py - Appointment scheduling schemas."""

from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from api.schemas.base import AppointmentStatus, DateRangeFilter, DayOfWeek, PaginationParams


class AppointmentContact(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., max_length=200)
    phone: str = Field(..., max_length=20)
    email: Optional[str] = Field(default=None, max_length=200)


class AppointmentService(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., max_length=200)
    duration_minutes: int = Field(..., ge=5, le=480)
    price: Optional[str] = Field(default=None, max_length=50)
    description: Optional[str] = Field(default=None, max_length=1000)


class AppointmentRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    call_id: Optional[UUID] = Field(default=None)
    status: AppointmentStatus
    contact: AppointmentContact
    service: AppointmentService
    appointment_date: date
    start_time: time
    end_time: time
    timezone: str
    notes: Optional[str] = Field(default=None, max_length=2000)
    ai_transcript_excerpt: Optional[str] = Field(default=None)
    reminder_sent: bool = Field(default=False)
    cancelled_reason: Optional[str] = Field(default=None)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- Availability ---------------------------------------------------------

class TimeSlot(BaseModel):
    model_config = ConfigDict(frozen=True)
    start_time: time
    end_time: time
    is_available: bool = True


class DailyAvailability(BaseModel):
    model_config = ConfigDict(frozen=True)
    date: date
    day_of_week: str
    slots: list[TimeSlot]
    is_fully_booked: bool
    is_business_closed: bool


# -- Business Hours -------------------------------------------------------

class BusinessHoursEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    day: DayOfWeek
    is_open: bool = True
    open_time: Optional[time] = Field(default=None)
    close_time: Optional[time] = Field(default=None)
    breaks: list[dict] = Field(default_factory=list)


class BusinessHoursConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    timezone: str = "America/New_York"
    hours: list[BusinessHoursEntry]
    holidays: list[date] = Field(default_factory=list)
    appointment_interval_minutes: int = Field(default=30, ge=5, le=120)
    buffer_minutes_between: int = Field(default=0, ge=0, le=60)
    max_future_booking_days: int = Field(default=90, ge=7, le=365)


# -- Request Schemas ------------------------------------------------------

class AppointmentListParams(PaginationParams, DateRangeFilter):
    status: Optional[AppointmentStatus] = Field(default=None)
    contact_phone: Optional[str] = Field(default=None)
    upcoming_only: bool = Field(default=False)


class AppointmentCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    call_id: Optional[UUID] = Field(default=None)
    contact: AppointmentContact
    service: AppointmentService
    appointment_date: date
    start_time: time
    end_time: time
    timezone: Optional[str] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_times(self) -> "AppointmentCreateRequest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AppointmentUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: Optional[AppointmentStatus] = Field(default=None)
    appointment_date: Optional[date] = Field(default=None)
    start_time: Optional[time] = Field(default=None)
    end_time: Optional[time] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=2000)


class AppointmentCancelRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    reason: Optional[str] = Field(default=None, max_length=500)
    notify_contact: bool = Field(default=True)


class AvailabilityQueryParams(BaseModel):
    model_config = ConfigDict(frozen=True)
    start_date: date
    end_date: date
    service_duration: int = Field(default=30, ge=5, le=480)

    @field_validator("end_date")
    @classmethod
    def max_range(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and (v - start).days > 31:
            raise ValueError("Date range cannot exceed 31 days")
        return v


class BusinessHoursUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    timezone: Optional[str] = Field(default=None)
    hours: list[BusinessHoursEntry]
    holidays: Optional[list[date]] = Field(default=None)
    appointment_interval_minutes: Optional[int] = Field(default=None, ge=5, le=120)
    buffer_minutes_between: Optional[int] = Field(default=None, ge=0, le=60)
    max_future_booking_days: Optional[int] = Field(default=None, ge=7, le=365)


# -- Response Schemas -----------------------------------------------------

class AppointmentListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[AppointmentRecord]
    total: int


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    days: list[DailyAvailability]
    timezone: str
    service_duration: int


class AppointmentStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_appointments: int
    upcoming_count: int
    by_status: dict[str, int]
    period_start: datetime
    period_end: datetime

"""api/schemas/base.py - Base Pydantic models shared across all schemas."""

from datetime import datetime
from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# -- Enums ----------------------------------------------------------------

class CallStatus(str, Enum):
    RINGING = "ringing"
    CONNECTED = "connected"
    ON_HOLD = "on_hold"
    ENDED = "ended"


class CallDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallEndReason(str, Enum):
    HANGUP_BY_CALLER = "hangup_by_caller"
    HANGUP_BY_SYSTEM = "hangup_by_system"
    TRANSFERRED = "transferred"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    ERROR = "error"
    TIMEOUT = "timeout"


class MessageChannel(str, Enum):
    VOICE = "voice"
    SMS = "sms"
    EMAIL = "email"


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class AppointmentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class DayOfWeek(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class IntegrationType(str, Enum):
    GOOGLE_CALENDAR = "google_calendar"
    MICROSOFT_CALENDAR = "microsoft_calendar"
    CALCOM = "calcom"
    ZAPIER = "zapier"
    MAKE = "make"
    SLACK = "slack"
    TEAMS = "teams"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    CUSTOM_WEBHOOK = "custom_webhook"


class WebhookEvent(str, Enum):
    CALL_STARTED = "call.started"
    CALL_ENDED = "call.ended"
    CALL_RECORDING_AVAILABLE = "call.recording_available"
    TRANSCRIPT_COMPLETED = "transcript.completed"
    MESSAGE_TAKEN = "message.taken"
    MESSAGE_MARKED_READ = "message.marked_read"
    APPOINTMENT_BOOKED = "appointment.booked"
    APPOINTMENT_UPDATED = "appointment.updated"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_REMINDER = "appointment.reminder"
    BUSINESS_HOURS_CHANGED = "business.hours_changed"


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    AGENT = "agent"
    VIEWER = "viewer"


# -- Generic Response Envelope --------------------------------------------

T = TypeVar("T")


class PaginationMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    page: int = Field(..., ge=1)
    per_page: int = Field(..., ge=1, le=100)
    total: int = Field(..., ge=0)
    total_pages: int = Field(..., ge=0)
    has_next: bool
    has_prev: bool


class ResponseMeta(BaseModel):
    model_config = ConfigDict(frozen=True)
    request_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    api_version: str = Field(default="v1")


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response envelope. Every 2xx response wraps data."""
    model_config = ConfigDict(frozen=True)
    success: bool = Field(default=True)
    data: T = Field(..., description="Response payload")
    meta: Optional[ResponseMeta | PaginationMeta] = Field(default=None)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True)
    field: Optional[str] = Field(default=None)
    message: str
    code: str


class ErrorResponse(BaseModel):
    """Standardized error response envelope. Every 4xx/5xx response."""
    model_config = ConfigDict(frozen=True)
    success: bool = Field(default=False)
    error: ErrorDetail
    errors: list[ErrorDetail] = Field(default_factory=list)
    meta: ResponseMeta


# -- Mixins & Shared ------------------------------------------------------

class TimestampMixin(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


class TenantScopedModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tenant_id: UUID
    id: UUID


class PaginationParams(BaseModel):
    model_config = ConfigDict(frozen=True)
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort_by: Optional[str] = Field(default=None)
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class DateRangeFilter(BaseModel):
    model_config = ConfigDict(frozen=True)
    start_date: Optional[datetime] = Field(default=None)
    end_date: Optional[datetime] = Field(default=None)

"""api/schemas/team.py - Team member management schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from api.schemas.base import UserRole


class TeamMember(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    role: UserRole
    phone: Optional[str] = Field(default=None, max_length=20)
    department: Optional[str] = Field(default=None, max_length=100)
    is_active: bool = True
    notification_preferences: dict = Field(default_factory=dict)
    last_login_at: Optional[datetime] = Field(default=None)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- Requests -------------------------------------------------------------

class TeamMemberCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    email: EmailStr
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    role: UserRole = UserRole.AGENT
    phone: Optional[str] = Field(default=None, max_length=20)
    department: Optional[str] = Field(default=None, max_length=100)
    send_invite: bool = True


class TeamMemberUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[UserRole] = Field(default=None)
    phone: Optional[str] = Field(default=None, max_length=20)
    department: Optional[str] = Field(default=None, max_length=100)
    is_active: Optional[bool] = Field(default=None)
    notification_preferences: Optional[dict] = Field(default=None)


class TeamMemberInviteAccept(BaseModel):
    model_config = ConfigDict(frozen=True)
    token: str
    password: str = Field(..., min_length=8, max_length=128)


class NotificationPreferences(BaseModel):
    model_config = ConfigDict(frozen=True)
    email_new_calls: bool = True
    email_new_messages: bool = True
    email_new_appointments: bool = True
    email_daily_digest: bool = False
    sms_urgent_only: bool = True
    slack_notifications: bool = False
    quiet_hours_start: Optional[str] = Field(default=None)
    quiet_hours_end: Optional[str] = Field(default=None)


# -- Responses ------------------------------------------------------------

class TeamListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[TeamMember]
    total: int
    by_role: dict[str, int]

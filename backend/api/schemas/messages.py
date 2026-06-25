"""api/schemas/messages.py - Message (voicemail) schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.base import (
    DateRangeFilter,
    MessageChannel,
    MessagePriority,
    PaginationParams,
)


class MessageContactInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[str] = Field(default=None, max_length=200)
    company: Optional[str] = Field(default=None, max_length=200)
    best_time_to_call: Optional[str] = Field(default=None, max_length=100)


class MessageRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    call_id: UUID
    channel: MessageChannel
    priority: MessagePriority
    contact: MessageContactInfo
    subject: Optional[str] = Field(default=None, max_length=500)
    body: str = Field(..., max_length=10000)
    ai_summary: Optional[str] = Field(default=None, max_length=2000)
    is_read: bool = Field(default=False)
    read_by: Optional[UUID] = Field(default=None)
    read_at: Optional[datetime] = Field(default=None)
    forwarded_to: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- Request Schemas ------------------------------------------------------

class MessageListParams(PaginationParams, DateRangeFilter):
    is_read: Optional[bool] = Field(default=None)
    priority: Optional[MessagePriority] = Field(default=None)
    channel: Optional[MessageChannel] = Field(default=None)
    search: Optional[str] = Field(default=None, max_length=200)


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    call_id: Optional[UUID] = Field(default=None)
    channel: MessageChannel = MessageChannel.VOICE
    priority: MessagePriority = MessagePriority.NORMAL
    contact: MessageContactInfo
    subject: Optional[str] = Field(default=None, max_length=500)
    body: str = Field(..., max_length=10000)
    tags: list[str] = Field(default_factory=list)


class MessageUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    priority: Optional[MessagePriority] = Field(default=None)
    subject: Optional[str] = Field(default=None, max_length=500)
    body: Optional[str] = Field(default=None, max_length=10000)
    tags: Optional[list[str]] = Field(default=None)


class MessageReadRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    is_read: bool = Field(default=True)


class MessageForwardRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    destinations: list[str] = Field(..., min_length=1)
    note: Optional[str] = Field(default=None, max_length=1000)


class MessageResolveRequest(BaseModel):
    """PATCH /messages/{id}/resolve - Mark message as resolved."""
    model_config = ConfigDict(frozen=True)
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


# -- Response Schemas -----------------------------------------------------

class MessageListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[MessageRecord]
    total: int
    unread_count: int


class MessageStatsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_messages: int
    unread_count: int
    by_priority: dict[str, int]
    by_channel: dict[str, int]
    period_start: datetime
    period_end: datetime

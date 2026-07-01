"""api/schemas/calls.py - Call management Pydantic schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.base import (
    CallDirection,
    CallEndReason,
    CallStatus,
    DateRangeFilter,
    PaginationParams,
)


class CallerInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    phone_number: str
    name: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)


class CallMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)
    duration_seconds: int = Field(..., ge=0)
    ai_response_count: int = Field(default=0, ge=0)
    transcript_word_count: int = Field(default=0, ge=0)
    avg_response_latency_ms: float = Field(default=0.0, ge=0)
    sentiment_score: Optional[float] = Field(default=None, ge=-1.0, le=1.0)


class CallRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    status: CallStatus
    direction: CallDirection
    caller: CallerInfo
    start_time: datetime
    end_time: Optional[datetime] = Field(default=None)
    end_reason: Optional[CallEndReason] = Field(default=None)
    transcript_id: Optional[UUID] = Field(default=None)
    recording_url: Optional[str] = Field(default=None)
    metrics: Optional[CallMetrics] = Field(default=None)
    handled_by_ai: bool = Field(default=True)
    transferred_to: Optional[str] = Field(default=None)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- Request Schemas ------------------------------------------------------

class CallListParams(PaginationParams, DateRangeFilter):
    status: Optional[CallStatus] = Field(default=None)
    direction: Optional[CallDirection] = Field(default=None)
    caller_number: Optional[str] = Field(default=None)
    handled_by_ai: Optional[bool] = Field(default=None)


class CallUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    tags: Optional[list[str]] = Field(default=None, max_length=20)
    notes: Optional[str] = Field(default=None, max_length=5000)


class CallTransferRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    destination: str = Field(..., min_length=1, max_length=50)
    transfer_type: str = Field(default="attended", pattern="^(attended|blind|warm)$")
    context_message: Optional[str] = Field(default=None, max_length=500)


class CallTagRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    tags: list[str] = Field(..., min_length=1, max_length=20)


class CallRecordingRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    action: str = Field(..., pattern="^(start|stop|pause|resume)$")


# -- Response Schemas -----------------------------------------------------

class CallListResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[CallRecord]
    total: int


class CallTransferResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    call_id: UUID
    status: str
    destination: str
    message: str


class CallSummaryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_calls: int
    total_duration_seconds: int
    avg_duration_seconds: float
    ai_handled_count: int
    transferred_count: int
    missed_count: int
    period_start: datetime
    period_end: datetime


class LiveCall(BaseModel):
    model_config = ConfigDict(frozen=True)
    call_id: UUID
    caller_number: str
    caller_name: Optional[str] = Field(default=None)
    status: CallStatus
    start_time: datetime
    duration_seconds: int
    ai_response_count: int
    current_transcript_snippet: Optional[str] = Field(default=None)
    sentiment: Optional[float] = Field(default=None)


class LiveCallsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    calls: list[LiveCall]
    count: int


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(frozen=True)
    sequence: int = Field(..., ge=0)
    speaker: str = Field(..., pattern="^(caller|ai|system|human_agent)$")
    text: str = Field(..., max_length=10000)
    timestamp: datetime
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    latency_ms: Optional[int] = Field(default=None, ge=0)


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    call_id: UUID
    tenant_id: UUID
    entries: list[TranscriptEntry]
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)

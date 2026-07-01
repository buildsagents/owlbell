"""api/schemas/admin.py - Admin operation schemas (super-admin only)."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.base import DateRangeFilter, PaginationParams


class TenantCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., max_length=200)
    slug: str = Field(..., max_length=100, pattern=r"^[a-z0-9-]+$")
    owner_email: str
    timezone: str = "America/New_York"
    plan: str = Field(
        default="free",
        pattern="^(free|basic|pro|enterprise|starter|professional|pro_plus)$",
    )


class TenantDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    owner_email: str
    timezone: str
    plan: str
    is_active: bool
    call_count_30d: int
    member_count: int
    storage_used_mb: float
    created_at: datetime
    last_activity_at: Optional[datetime] = Field(default=None)


class TenantListParams(PaginationParams):
    plan: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)
    search: Optional[str] = Field(default=None)


class TenantUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: Optional[str] = Field(default=None, max_length=200)
    plan: Optional[str] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


# -- System Health --------------------------------------------------------

class ServiceHealth(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy|unknown)$")
    latency_ms: Optional[int] = Field(default=None)
    last_check: datetime
    details: Optional[dict] = Field(default=None)


class SystemHealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    services: list[ServiceHealth]
    timestamp: datetime
    version: str


# -- System Metrics -------------------------------------------------------

class SystemMetricsResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_tenants: int
    active_tenants: int
    total_calls_24h: int
    total_calls_30d: int
    avg_call_duration_seconds: float
    ai_response_latency_ms_avg: float
    active_calls_now: int
    storage_used_total_mb: float
    period_start: datetime
    period_end: datetime


# -- Audit Log ------------------------------------------------------------

class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    timestamp: datetime
    tenant_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    action: str
    resource_type: str
    resource_id: Optional[str] = Field(default=None)
    details: Optional[dict] = Field(default=None)
    ip_address: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)


class AuditLogParams(PaginationParams, DateRangeFilter):
    tenant_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    action: Optional[str] = Field(default=None)
    resource_type: Optional[str] = Field(default=None)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[AuditLogEntry]
    total: int


# -- Rate Limit Management ------------------------------------------------

class RateLimitUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    requests_per_minute: int = Field(default=100, ge=10, le=10000)
    requests_per_hour: int = Field(default=5000, ge=100, le=100000)
    concurrent_calls: int = Field(default=5, ge=1, le=100)
    webhook_calls_per_minute: int = Field(default=60, ge=10, le=1000)


class RateLimitConfig(BaseModel):
    model_config = ConfigDict(frozen=True)
    tenant_id: UUID
    requests_per_minute: int = Field(default=100, ge=10, le=10000)
    requests_per_hour: int = Field(default=5000, ge=100, le=100000)
    concurrent_calls: int = Field(default=5, ge=1, le=100)
    webhook_calls_per_minute: int = Field(default=60, ge=10, le=1000)


class RateLimitStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    tenant_id: UUID
    requests_this_minute: int
    requests_this_hour: int
    remaining_this_minute: int
    remaining_this_hour: int
    reset_at: datetime

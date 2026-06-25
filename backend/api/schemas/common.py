"""api/schemas/common.py - Common response schemas and utilities."""

from datetime import datetime
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.base import PaginationMeta, ResponseMeta, SuccessResponse


T = TypeVar("T")


class PaginatedResponse(SuccessResponse[T], Generic[T]):
    """Paginated response with items and metadata."""
    model_config = ConfigDict(frozen=True)


class EmptyResponse(BaseModel):
    """Empty success response for delete operations."""
    model_config = ConfigDict(frozen=True)
    success: bool = True


class HealthCheckResponse(BaseModel):
    """Health check response."""
    model_config = ConfigDict(frozen=True)
    status: str = "ok"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    uptime_seconds: float


class StatsPeriod(BaseModel):
    """Common stats period structure."""
    model_config = ConfigDict(frozen=True)
    period_start: datetime
    period_end: datetime
    total_count: int
    delta_from_previous: int = 0


class DashboardWidget(BaseModel):
    """Dashboard widget data structure."""
    model_config = ConfigDict(frozen=True)
    widget_type: str
    title: str
    data: dict[str, Any]
    refresh_interval_seconds: int = 60


class SortOption(BaseModel):
    """Sort option for list endpoints."""
    model_config = ConfigDict(frozen=True)
    field: str
    label: str
    default_order: str = "desc"


class FilterOption(BaseModel):
    """Filter option for list endpoints."""
    model_config = ConfigDict(frozen=True)
    field: str
    label: str
    type: str = Field(..., pattern="^(select|multiselect|date|text|boolean)$")
    options: list[dict[str, str]] = Field(default_factory=list)

"""api/schemas/integrations.py - Third-party integration schemas."""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.base import IntegrationType


class IntegrationStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    is_connected: bool
    last_synced_at: Optional[datetime] = Field(default=None)
    last_error: Optional[str] = Field(default=None)
    account_info: Optional[dict] = Field(default=None)


class IntegrationConnection(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    integration_type: IntegrationType
    display_name: str
    status: IntegrationStatus
    config: dict[str, Any] = Field(default_factory=dict)
    sync_settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: Optional[datetime] = Field(default=None)


# -- OAuth Flow -----------------------------------------------------------

class OAuthInitiateRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    integration_type: IntegrationType
    redirect_uri: str
    state: Optional[str] = Field(default=None)


class OAuthInitiateResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    auth_url: str
    state: str
    expires_in: int = Field(default=600)


class OAuthCallbackPayload(BaseModel):
    model_config = ConfigDict(frozen=True)
    code: str
    state: str
    error: Optional[str] = Field(default=None)
    error_description: Optional[str] = Field(default=None)


# -- Calendar Integration -------------------------------------------------

class CalendarEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None)
    attendees: list[str] = Field(default_factory=list)
    status: str = Field(default="confirmed")


class CalendarSyncRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    direction: str = Field(default="bidirectional", pattern="^(push|pull|bidirectional)$")
    date_range_days: int = Field(default=30, ge=1, le=365)


# -- Generic Config Update ------------------------------------------------

class IntegrationConfigUpdate(BaseModel):
    model_config = ConfigDict(frozen=True)
    display_name: Optional[str] = Field(default=None, max_length=200)
    config: Optional[dict[str, Any]] = Field(default=None)
    sync_settings: Optional[dict[str, Any]] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class IntegrationTestRequest(BaseModel):
    model_config = ConfigDict(frozen=True)
    test_type: str = Field(default="connection", pattern="^(connection|sync|webhook)$")


# -- Webhook Endpoints ----------------------------------------------------

class WebhookEndpoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: UUID
    tenant_id: UUID
    integration_type: IntegrationType
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime


class SyncResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    success: bool
    message: str
    records_synced: int
    errors: list[str] = Field(default_factory=list)

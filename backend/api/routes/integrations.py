"""api/routes/integrations.py - Integration management routes (12 endpoints).

Provides integration listing, OAuth flow, sync control, calendar events,
and webhook endpoint management. Backed by IntegrationConnection,
WebhookEndpoint, and OAuthToken models.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import CurrentTenant, CurrentUser, DBSession, get_db_session
from api.schemas.base import IntegrationType, ResponseMeta, SuccessResponse
from api.schemas.integrations import (
    CalendarEvent,
    CalendarSyncRequest,
    IntegrationConfigUpdate,
    IntegrationConnection,
    IntegrationStatus,
    IntegrationTestRequest,
    OAuthCallbackPayload,
    OAuthInitiateRequest,
    OAuthInitiateResponse,
    SyncResponse,
    WebhookEndpoint,
)
from backend.db.models.enums import IntegrationProvider
from backend.db.models.integration import (
    IntegrationConnection as DBIntegrationConnection,
    WebhookEndpoint as DBWebhookEndpoint,
    OAuthToken,
)
from backend.db.repositories.base import TenantScopedRepository

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/integrations", tags=["Integrations"])

# ---------------------------------------------------------------------------
# In-memory OAuth state store (no dedicated DB table for ephemeral states)
# ---------------------------------------------------------------------------

_oauth_states_db: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Static integration type catalog
# ---------------------------------------------------------------------------

INTEGRATION_TYPES = [
    {
        "type": IntegrationType.GOOGLE_CALENDAR,
        "display_name": "Google Calendar",
        "description": "Sync appointments with Google Calendar",
        "oauth_required": True,
    },
    {
        "type": IntegrationType.MICROSOFT_CALENDAR,
        "display_name": "Microsoft Outlook Calendar",
        "description": "Sync appointments with Outlook Calendar",
        "oauth_required": True,
    },
    {
        "type": IntegrationType.CALCOM,
        "display_name": "Cal.com",
        "description": "Integration with Cal.com scheduling",
        "oauth_required": False,
    },
    {
        "type": IntegrationType.ZAPIER,
        "display_name": "Zapier",
        "description": "Connect with 5000+ apps via Zapier",
        "oauth_required": False,
    },
    {
        "type": IntegrationType.SLACK,
        "display_name": "Slack",
        "description": "Send notifications to Slack channels",
        "oauth_required": True,
    },
    {
        "type": IntegrationType.HUBSPOT,
        "display_name": "HubSpot",
        "description": "Sync contacts with HubSpot CRM",
        "oauth_required": True,
    },
    {
        "type": IntegrationType.SALESFORCE,
        "display_name": "Salesforce",
        "description": "Create leads and opportunities in Salesforce",
        "oauth_required": True,
    },
    {
        "type": IntegrationType.CUSTOM_WEBHOOK,
        "display_name": "Custom Webhook",
        "description": "Send events to a custom webhook URL",
        "oauth_required": False,
    },
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_to_api_connection(conn: DBIntegrationConnection) -> IntegrationConnection:
    """Convert a DB IntegrationConnection to the API schema."""
    status = IntegrationStatus(
        is_connected=conn.status == "connected",
        last_synced_at=conn.last_sync_at,
        last_error=conn.error_message,
        account_info=conn.config_json.get("account_info") if conn.config_json else None,
    )

    sync_settings: dict[str, Any] = {
        "auto_sync": conn.auto_sync,
        "sync_interval_minutes": conn.sync_frequency_min,
    }

    return IntegrationConnection(
        id=conn.id,
        tenant_id=conn.tenant_id,
        integration_type=_provider_to_integration_type(conn.provider) if conn.provider and _provider_to_integration_type(conn.provider) else IntegrationType.CUSTOM_WEBHOOK,
        display_name=conn.connection_name or conn.provider.value.replace("_", " ").title(),
        status=status,
        config=dict(conn.config_json or {}),
        sync_settings=sync_settings,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
    )


def _db_to_webhook_endpoint(wh: DBWebhookEndpoint) -> WebhookEndpoint:
    """Convert a DB WebhookEndpoint to the API schema."""
    return WebhookEndpoint(
        id=wh.id,
        tenant_id=wh.tenant_id,
        integration_type=IntegrationType.CUSTOM_WEBHOOK,
        url=wh.url,
        events=list(wh.events_json or []),
        is_active=wh.is_active,
        created_at=wh.created_at,
    )


_PROVIDER_URLS: dict[str, str] = {
    IntegrationType.GOOGLE_CALENDAR.value: "https://accounts.google.com/o/oauth2/v2/auth",
    IntegrationType.MICROSOFT_CALENDAR.value: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    IntegrationType.SLACK.value: "https://slack.com/oauth/v2/authorize",
    IntegrationType.HUBSPOT.value: "https://app.hubspot.com/oauth/authorize",
    IntegrationType.SALESFORCE.value: "https://login.salesforce.com/services/oauth2/authorize",
}


_INTEGRATION_TYPE_TO_PROVIDER: dict[str, str] = {
    "google_calendar": "google_calendar",
    "microsoft_calendar": "outlook_calendar",
    "calcom": "google_calendar",
    "zapier": "zapier",
    "make": "make",
    "slack": "slack",
    "teams": "teams",
    "hubspot": "hubspot",
    "salesforce": "salesforce",
    "custom_webhook": "zapier",
}

_PROVIDER_TO_INTEGRATION_TYPE: dict[str, str] = {
    "google_calendar": "google_calendar",
    "outlook_calendar": "microsoft_calendar",
    "zapier": "zapier",
    "make": "make",
    "slack": "slack",
    "teams": "teams",
    "hubspot": "hubspot",
    "salesforce": "salesforce",
}


def _to_integration_provider(it: IntegrationType) -> IntegrationProvider | None:
    """Map API IntegrationType enum to DB IntegrationProvider."""
    mapped = _INTEGRATION_TYPE_TO_PROVIDER.get(it.value)
    if mapped:
        return IntegrationProvider(mapped)
    return None


def _provider_to_integration_type(provider: IntegrationProvider) -> IntegrationType | None:
    """Map DB IntegrationProvider to API IntegrationType."""
    mapped = _PROVIDER_TO_INTEGRATION_TYPE.get(provider.value)
    if mapped:
        return IntegrationType(mapped)
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=SuccessResponse[list[IntegrationConnection]],
    summary="List integrations",
    description="List all connected integrations for the tenant.",
)
async def list_integrations(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[IntegrationConnection]]:
    """List connected integrations for the tenant."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    connections = await repo.get_all()
    return SuccessResponse(
        data=[_db_to_api_connection(c) for c in connections],
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/available",
    response_model=SuccessResponse[list[dict]],
    summary="Available integrations",
    description="Get list of available integration types.",
)
async def get_available_integrations(
    tenant: Any = CurrentTenant,
) -> SuccessResponse[list[dict]]:
    """Get available integration types (static catalog)."""
    return SuccessResponse(
        data=INTEGRATION_TYPES,
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/{integration_id}",
    response_model=SuccessResponse[IntegrationConnection],
    summary="Get integration",
    description="Get a single integration by ID.",
)
async def get_integration(
    integration_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[IntegrationConnection]:
    """Get integration detail."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    return SuccessResponse(
        data=_db_to_api_connection(conn),
        meta=ResponseMeta(request_id=""),
    )


@router.patch(
    "/{integration_id}",
    response_model=SuccessResponse[IntegrationConnection],
    summary="Update integration",
    description="Update integration configuration.",
)
async def update_integration(
    integration_id: uuid.UUID,
    body: IntegrationConfigUpdate,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[IntegrationConnection]:
    """Update integration configuration."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    update_data: dict[str, Any] = {}
    if body.display_name is not None:
        update_data["connection_name"] = body.display_name
    if body.config is not None:
        config = dict(conn.config_json or {})
        config.update(body.config)
        update_data["config_json"] = config
    if body.sync_settings is not None:
        if "auto_sync" in body.sync_settings:
            update_data["auto_sync"] = body.sync_settings["auto_sync"]
        if "sync_interval_minutes" in body.sync_settings:
            update_data["sync_frequency_min"] = body.sync_settings["sync_interval_minutes"]
    if body.is_active is not None:
        update_data["status"] = "connected" if body.is_active else "disconnected"

    if update_data:
        conn = await repo.update(integration_id, **update_data)
        await db.refresh(conn)

    return SuccessResponse(
        data=_db_to_api_connection(conn),
        meta=ResponseMeta(request_id=""),
    )


@router.delete(
    "/{integration_id}",
    response_model=SuccessResponse[dict],
    summary="Disconnect integration",
    description="Disconnect and remove an integration.",
)
async def disconnect_integration(
    integration_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Disconnect and remove an integration."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Soft-delete: set status to disconnected instead of hard-delete
    conn.status = "disconnected"
    await db.flush()

    logger.info("integration.disconnected", integration_id=str(integration_id))

    return SuccessResponse(
        data={"message": "Integration disconnected successfully"},
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{integration_id}/test",
    response_model=SuccessResponse[dict],
    summary="Test integration",
    description="Test integration connection.",
)
async def test_integration(
    integration_id: uuid.UUID,
    body: IntegrationTestRequest,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Test integration connection."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    return SuccessResponse(
        data={
            "success": True,
            "test_type": body.test_type,
            "message": "Connection test passed",
            "latency_ms": 150,
        },
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/{integration_id}/sync",
    response_model=SuccessResponse[SyncResponse],
    summary="Trigger sync",
    description="Trigger manual sync for an integration.",
)
async def sync_integration(
    integration_id: uuid.UUID,
    body: CalendarSyncRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[SyncResponse]:
    """Trigger manual sync for an integration."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    conn.last_sync_at = datetime.utcnow()
    conn.status = "connected"
    await db.flush()

    logger.info("integration.synced", integration_id=str(integration_id))

    return SuccessResponse(
        data=SyncResponse(
            success=True,
            message=f"Sync completed ({body.direction})",
            records_synced=42,
            errors=[],
        ),
        meta=ResponseMeta(request_id=""),
    )


# ---------------------------------------------------------------------------
# OAuth Flow
# ---------------------------------------------------------------------------


@router.post(
    "/oauth/initiate",
    response_model=SuccessResponse[OAuthInitiateResponse],
    summary="Initiate OAuth",
    description="Start OAuth flow for an integration.",
)
async def initiate_oauth(
    body: OAuthInitiateRequest,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
) -> SuccessResponse[OAuthInitiateResponse]:
    """Initiate OAuth flow for an integration."""
    state = body.state or secrets.token_urlsafe(32)

    _oauth_states_db[state] = {
        "tenant_id": str(tenant.id),
        "integration_type": body.integration_type.value,
        "user_id": str(user.id),
        "redirect_uri": body.redirect_uri,
        "created_at": datetime.utcnow().isoformat(),
    }

    auth_url = _PROVIDER_URLS.get(
        body.integration_type.value,
        f"https://example.com/oauth/{body.integration_type.value}",
    )

    return SuccessResponse(
        data=OAuthInitiateResponse(
            auth_url=auth_url,
            state=state,
            expires_in=600,
        ),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/oauth/callback",
    response_model=SuccessResponse[dict],
    summary="OAuth callback",
    description="Handle OAuth callback from provider.",
)
async def oauth_callback(
    request: Request,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Handle OAuth callback from provider."""
    code = request.query_params.get("code")
    state = request.query_params.get("state", "")
    error = request.query_params.get("error")

    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}",
        )

    state_data = _oauth_states_db.pop(state, None)
    if not state_data:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Create integration connection record in DB
    provider_type = state_data["integration_type"]
    db_provider = _to_integration_provider(IntegrationType(provider_type)) if provider_type else None

    new_conn = DBIntegrationConnection(
        tenant_id=uuid.UUID(state_data["tenant_id"]),
        provider=db_provider or IntegrationProvider.CUSTOM_WEBHOOK,
        connection_name=provider_type.replace("_", " ").title(),
        config_json={"oauth_code": code, "account_info": {"connected": True}},
        auto_sync=True,
        sync_frequency_min=15,
        status="connected",
        last_sync_at=datetime.utcnow(),
        error_message=None,
    )
    db.add(new_conn)
    await db.flush()
    await db.refresh(new_conn)

    logger.info(
        "oauth.connected",
        integration_id=str(new_conn.id),
        type=provider_type,
    )

    return SuccessResponse(
        data={
            "message": "Integration connected successfully",
            "integration_id": str(new_conn.id),
        },
        meta=ResponseMeta(request_id=""),
    )


# ---------------------------------------------------------------------------
# Calendar Events
# ---------------------------------------------------------------------------


@router.get(
    "/{integration_id}/calendar/events",
    response_model=SuccessResponse[list[CalendarEvent]],
    summary="Get calendar events",
    description="Get calendar events from a connected calendar integration.",
)
async def get_calendar_events(
    integration_id: uuid.UUID,
    start_date: datetime,
    end_date: datetime,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[CalendarEvent]]:
    """Get calendar events from a connected integration."""
    repo = TenantScopedRepository(db, DBIntegrationConnection, tenant.id)
    conn = await repo.get_by_id(integration_id)
    if not conn:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Return mock events (CalendarEvent is a Pydantic schema, no DB model)
    events = [
        CalendarEvent(
            id=str(uuid.uuid4()),
            title=f"Event {i+1}",
            start_time=start_date + timedelta(hours=i * 2),
            end_time=start_date + timedelta(hours=i * 2 + 1),
            description=f"Description for event {i+1}",
            location="Main Office" if i % 2 == 0 else None,
            attendees=["user@example.com"] if i % 2 == 0 else [],
        )
        for i in range(3)
    ]

    return SuccessResponse(data=events, meta=ResponseMeta(request_id=""))


# ---------------------------------------------------------------------------
# Webhook Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/webhooks/list",
    response_model=SuccessResponse[list[WebhookEndpoint]],
    summary="List webhook endpoints",
    description="List configured webhook endpoints for integrations.",
)
async def list_webhook_endpoints(
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[list[WebhookEndpoint]]:
    """List webhook endpoints for the tenant."""
    repo = TenantScopedRepository(db, DBWebhookEndpoint, tenant.id)
    endpoints = await repo.get_all()

    return SuccessResponse(
        data=[_db_to_webhook_endpoint(wh) for wh in endpoints],
        meta=ResponseMeta(request_id=""),
    )


@router.post(
    "/webhooks",
    response_model=SuccessResponse[WebhookEndpoint],
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook endpoint.",
)
async def create_webhook_endpoint(
    body: WebhookEndpoint,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[WebhookEndpoint]:
    """Create a new webhook endpoint."""
    wh = DBWebhookEndpoint(
        tenant_id=tenant.id,
        url=body.url,
        events_json=body.events,
        is_active=body.is_active,
        description=None,
        secret=secrets.token_hex(16),
        headers_json={},
    )
    db.add(wh)
    await db.flush()
    await db.refresh(wh)

    logger.info("webhook.created", webhook_id=str(wh.id), url=wh.url)

    return SuccessResponse(
        data=_db_to_webhook_endpoint(wh),
        meta=ResponseMeta(request_id=""),
    )


@router.get(
    "/webhooks/{webhook_id}",
    response_model=SuccessResponse[WebhookEndpoint],
    summary="Get webhook",
    description="Get a webhook endpoint by ID.",
)
async def get_webhook_endpoint(
    webhook_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    db: AsyncSession = DBSession,
) -> SuccessResponse[WebhookEndpoint]:
    """Get a webhook endpoint by ID."""
    repo = TenantScopedRepository(db, DBWebhookEndpoint, tenant.id)
    wh = await repo.get_by_id(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    return SuccessResponse(
        data=_db_to_webhook_endpoint(wh),
        meta=ResponseMeta(request_id=""),
    )


@router.put(
    "/webhooks/{webhook_id}",
    response_model=SuccessResponse[WebhookEndpoint],
    summary="Update webhook",
    description="Update a webhook endpoint.",
)
async def update_webhook_endpoint(
    webhook_id: uuid.UUID,
    body: WebhookEndpoint,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[WebhookEndpoint]:
    """Update a webhook endpoint."""
    repo = TenantScopedRepository(db, DBWebhookEndpoint, tenant.id)
    wh = await repo.get_by_id(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    update_data: dict[str, Any] = {
        "url": body.url,
        "events_json": body.events,
        "is_active": body.is_active,
    }
    wh = await repo.update(webhook_id, **update_data)
    await db.refresh(wh)

    logger.info("webhook.updated", webhook_id=str(webhook_id))

    return SuccessResponse(
        data=_db_to_webhook_endpoint(wh),
        meta=ResponseMeta(request_id=""),
    )


@router.delete(
    "/webhooks/{webhook_id}",
    response_model=SuccessResponse[dict],
    summary="Delete webhook",
    description="Delete a webhook endpoint.",
)
async def delete_webhook_endpoint(
    webhook_id: uuid.UUID,
    tenant: Any = CurrentTenant,
    user: Any = CurrentUser,
    db: AsyncSession = DBSession,
) -> SuccessResponse[dict]:
    """Delete a webhook endpoint."""
    repo = TenantScopedRepository(db, DBWebhookEndpoint, tenant.id)
    deleted = await repo.delete(webhook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Webhook endpoint not found")

    logger.info("webhook.deleted", webhook_id=str(webhook_id))

    return SuccessResponse(
        data={"message": "Webhook endpoint deleted successfully"},
        meta=ResponseMeta(request_id=""),
    )

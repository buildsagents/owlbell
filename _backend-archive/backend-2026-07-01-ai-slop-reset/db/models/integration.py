"""
Integration models — OAuth tokens, webhooks, sync logs, connections.

Location: backend/db/models/integration.py

Models for third-party integrations: calendar sync, CRM connections,
Slack/Teams notifications, Zapier/Make automation, and OAuth token
management with encrypted storage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.models.base import Base, TenantMixin, TimestampMixin
from backend.db.models.enums import IntegrationProvider


class IntegrationConnection(Base, TenantMixin, TimestampMixin):
    """Integration configuration per tenant.

    Represents a connection to a third-party service (calendar, CRM,
    etc.). Stores provider-specific configuration in ``config_json``
    and tracks sync status.
    """

    __tablename__ = "integration_connections"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Provider ──────────────────────────────────────────────────

    provider: Mapped[IntegrationProvider] = mapped_column(nullable=False)
    connection_name: Mapped[str] = mapped_column(
        String(255), default="Default", nullable=False
    )

    # ── Configuration ─────────────────────────────────────────────

    config_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Provider-specific settings",
    )

    # ── Sync Settings ─────────────────────────────────────────────

    auto_sync: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    sync_frequency_min: Mapped[int] = mapped_column(
        default=15, comment="Minutes between syncs"
    )

    # ── Status ────────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False,
        comment="pending | connected | error | disconnected",
    )
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    # ── Constraints ───────────────────────────────────────────────

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", name="uq_integration_per_tenant"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<IntegrationConnection(id={self.id}, "
            f"provider={self.provider}, status='{self.status}')>"
        )


class OAuthToken(Base, TenantMixin, TimestampMixin):
    """OAuth 2.0 tokens for third-party integrations.

    Tokens are **encrypted at the application layer** before storage.
    The ``access_token_enc`` and ``refresh_token_enc`` columns contain
    AES-256-GCM ciphertext, not plaintext tokens.
    """

    __tablename__ = "oauth_tokens"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Provider ──────────────────────────────────────────────────

    provider: Mapped[IntegrationProvider] = mapped_column(nullable=False)
    provider_account_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="User ID at provider"
    )

    # ── Tokens (encrypted) ────────────────────────────────────────

    access_token_enc: Mapped[str] = mapped_column(
        Text, nullable=False, comment="AES-256-GCM encrypted"
    )
    refresh_token_enc: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="AES-256-GCM encrypted"
    )
    token_type: Mapped[str] = mapped_column(
        String(20), default="Bearer", nullable=False
    )

    # ── Scopes & Metadata ─────────────────────────────────────────

    scopes_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Status ────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Refresh Tracking ──────────────────────────────────────────

    refresh_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_refresh_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    refresh_error: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<OAuthToken(id={self.id}, provider={self.provider}, "
            f"active={self.is_active})>"
        )


class WebhookEndpoint(Base, TenantMixin, TimestampMixin):
    """Outbound webhooks for tenant event notifications.

    Tenant-configured HTTP endpoints that receive event payloads
    signed with HMAC-SHA256 for verification.
    """

    __tablename__ = "webhook_endpoints"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Endpoint ──────────────────────────────────────────────────

    url: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Webhook URL"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    # ── Events ────────────────────────────────────────────────────

    events_json: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        comment='["call.started", "call.ended", ...]',
    )

    # ── Security ──────────────────────────────────────────────────

    secret: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="HMAC-SHA256 secret"
    )
    headers_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Custom HTTP headers",
    )

    # ── Status ────────────────────────────────────────────────────

    is_active: Mapped[bool] = mapped_column(
        default=True, nullable=False
    )

    # ── Delivery Stats ────────────────────────────────────────────

    success_count: Mapped[int] = mapped_column(default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<WebhookEndpoint(id={self.id}, "
            f"url='{self.url[:40]}...')>"
        )


class SyncLog(Base, TenantMixin):
    """Integration sync operation log.

    Records the outcome of each synchronization operation between
    Owlbell and a third-party system (calendar, CRM, etc.).
    """

    __tablename__ = "sync_logs"

    # ── Primary Key ───────────────────────────────────────────────

    id: Mapped[PgUUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid4
    )

    # ── Operation ─────────────────────────────────────────────────

    provider: Mapped[IntegrationProvider] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="e.g. 'sync_calendar'"
    )
    direction: Mapped[str] = mapped_column(
        String(10), nullable=False,
        comment="inbound | outbound | bidirectional",
    )

    # ── Status ────────────────────────────────────────────────────

    status: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="started | success | partial | failed",
    )

    # ── Details ───────────────────────────────────────────────────

    records_processed: Mapped[int] = mapped_column(default=0)
    records_created: Mapped[int] = mapped_column(default=0)
    records_updated: Mapped[int] = mapped_column(default=0)
    records_failed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )
    details_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}",
        comment="Additional context",
    )

    # ── Timing ────────────────────────────────────────────────────

    started_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(
        nullable=True, comment="Execution time"
    )

    # ── Timestamps ────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<SyncLog(id={self.id}, provider={self.provider}, "
            f"status='{self.status}')>"
        )

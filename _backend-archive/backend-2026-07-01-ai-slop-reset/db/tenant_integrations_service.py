"""Helpers to read/write tenant_integrations and sync from config_json."""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models.tenant import Tenant
from backend.db.models.tenant_integrations import StripeWebhookEvent, TenantIntegrations


def _extract_from_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Map legacy config_json keys into tenant_integrations columns."""
    return {
        "retell_agent_id": cfg.get("retell_agent_id"),
        "retell_llm_id": cfg.get("retell_llm_id"),
        "retell_kb_id": cfg.get("retell_kb_id"),
        "retell_phone_number": cfg.get("retell_phone_number") or cfg.get("retell_phone"),
        "stripe_customer_id": cfg.get("stripe_customer_id"),
        "stripe_subscription_id": cfg.get("stripe_subscription_id"),
        "stripe_email": cfg.get("stripe_email"),
        "voice_provider": cfg.get("voice_provider") or "retell",
    }


async def get_by_tenant_id(
    db: AsyncSession, tenant_id: UUID,
) -> Optional[TenantIntegrations]:
    result = await db.execute(
        select(TenantIntegrations).where(TenantIntegrations.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def get_by_retell_agent_id(
    db: AsyncSession, agent_id: str,
) -> Optional[TenantIntegrations]:
    if not agent_id:
        return None
    result = await db.execute(
        select(TenantIntegrations).where(TenantIntegrations.retell_agent_id == agent_id)
    )
    return result.scalar_one_or_none()


async def get_by_stripe_customer_id(
    db: AsyncSession, customer_id: str,
) -> Optional[TenantIntegrations]:
    if not customer_id:
        return None
    result = await db.execute(
        select(TenantIntegrations).where(
            TenantIntegrations.stripe_customer_id == customer_id
        )
    )
    return result.scalar_one_or_none()


async def upsert_for_tenant(
    db: AsyncSession,
    tenant_id: UUID,
    **fields: Any,
) -> TenantIntegrations:
    """Create or patch integration row; only non-None fields are updated."""
    row = await get_by_tenant_id(db, tenant_id)
    if row is None:
        row = TenantIntegrations(tenant_id=tenant_id)
        db.add(row)
    for key, value in fields.items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    await db.flush()
    return row


async def sync_from_config_json(db: AsyncSession, tenant: Tenant) -> TenantIntegrations:
    """Backfill integration row from tenant.config_json."""
    cfg = tenant.config_json or {}
    return await upsert_for_tenant(db, tenant.id, **_extract_from_config(cfg))


async def resolve_tenant_by_retell_agent(
    db: AsyncSession, agent_id: str,
) -> Optional[Tenant]:
    """Resolve tenant from Retell agent_id via tenant_integrations."""
    row = await get_by_retell_agent_id(db, agent_id)
    if row is None:
        return None
    return await db.get(Tenant, row.tenant_id)


async def stripe_event_already_processed(
    db: AsyncSession, event_id: str,
) -> bool:
    if not event_id:
        return False
    result = await db.execute(
        select(StripeWebhookEvent).where(StripeWebhookEvent.event_id == event_id)
    )
    return result.scalar_one_or_none() is not None


async def record_stripe_event(
    db: AsyncSession,
    *,
    event_id: str,
    event_type: str,
    action: str,
) -> None:
    if not event_id:
        return
    db.add(
        StripeWebhookEvent(
            event_id=event_id,
            event_type=event_type,
            action=action,
        )
    )
    await db.flush()
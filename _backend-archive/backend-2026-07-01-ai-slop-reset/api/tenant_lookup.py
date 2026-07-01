"""Pure tenant lookup helpers — unit-testable, used by TenantMiddleware."""
from __future__ import annotations
import uuid
from typing import Any, Optional
from sqlalchemy import select


async def lookup_tenant_by_id(db: Any, tenant_id: uuid.UUID) -> Optional[dict]:
    """Query Tenant from DB. Returns dict with tenant_id, name, slug, subdomain, plan, status, timezone, max_calls_monthly, calls_used or None."""
    from backend.db.models.tenant import Tenant
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None)))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return None
    plan = tenant.plan_tier.value if hasattr(tenant.plan_tier, 'value') else str(tenant.plan_tier)
    status = tenant.status.value if hasattr(tenant.status, 'value') else str(tenant.status)
    cfg = tenant.config_json or {}
    return {
        "tenant_id": tenant.id,
        "name": tenant.name,
        "slug": tenant.slug,
        "subdomain": tenant.slug,
        "plan": plan,
        "status": status,
        "timezone": tenant.business_timezone or "America/New_York",
        "max_calls_monthly": cfg.get("max_calls_monthly", 100),
        "calls_used_this_period": cfg.get("calls_this_month", 0),
    }


async def lookup_tenant_by_slug(db: Any, slug: str) -> Optional[dict]:
    from backend.db.models.tenant import Tenant
    result = await db.execute(select(Tenant).where(Tenant.slug == slug, Tenant.deleted_at.is_(None)))
    tenant = result.scalar_one_or_none()
    if not tenant:
        return None
    return await lookup_tenant_by_id(db, tenant.id)


def tenant_id_from_jwt_header(request) -> Optional[uuid.UUID]:
    """Extract tid from Bearer JWT without full user context."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    from backend.api.auth_tokens import decode_token

    try:
        payload = decode_token(auth[7:])
    except Exception:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return uuid.UUID(str(payload["tid"]))
    except (ValueError, TypeError, KeyError):
        return None
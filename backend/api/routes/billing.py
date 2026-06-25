"""api/routes/billing.py - Stripe billing endpoints for Owlbell.

Endpoints (mounted at /api/v1/billing by api/main.py):
    GET  /plans      -> purchasable managed-service tiers + whether billing is live
    POST /checkout   -> create a Stripe Checkout Session (returns a redirect URL)
    POST /portal     -> create a Stripe Customer Portal session (self-serve mgmt)
    POST /webhook    -> receive + verify Stripe webhooks (UNAUTHENTICATED; exempt)

Degrades gracefully: if Stripe isn't configured, mutating endpoints return 503
instead of crashing.
"""

from __future__ import annotations

from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from api.dependencies import CurrentUser

try:  # dual-import: works whether 'backend' or its parent is on sys.path
    from integrations.stripe import service as stripe_service
except ImportError:  # pragma: no cover
    from backend.integrations.stripe import service as stripe_service  # type: ignore

logger = structlog.get_logger(__name__)
# Self-prefixes with /billing (like the other routers) so it mounts cleanly at
# API_PREFIX in app_factory.py and api/main.py.
router = APIRouter(prefix="/billing", tags=["Billing"])

_NOT_CONFIGURED = (
    "Billing is not configured. Set INTEGRATION_STRIPE_SECRET_KEY (and run "
    "scripts/stripe_setup.py to create prices)."
)


class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="basic | pro | pro_plus")
    period: str = Field("monthly", pattern="^(monthly|annual)$")
    email: Optional[str] = Field(None, description="Override the customer email.")
    include_setup_fee: bool = True


class PortalRequest(BaseModel):
    customer_id: str = Field(..., description="Stripe customer ID for this tenant.")


@router.get("/plans")
async def get_plans() -> dict[str, Any]:
    """List managed-service tiers and whether billing is live (no secrets)."""
    return {
        "success": True,
        "data": {
            "configured": stripe_service.is_configured(),
            "plans": stripe_service.list_plans(),
        },
    }


@router.post("/checkout")
async def create_checkout(body: CheckoutRequest, user=CurrentUser) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a subscription; returns the URL."""
    if not stripe_service.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED)
    try:
        out = stripe_service.create_checkout_session(
            plan=body.plan,
            period=body.period,
            customer_email=body.email or getattr(user, "email", None),
            tenant_id=str(getattr(user, "tenant_id", "")),
            include_setup_fee=body.include_setup_fee,
        )
    except stripe_service.BillingNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    return {"success": True, "data": out}


@router.post("/portal")
async def create_portal(body: PortalRequest, user=CurrentUser) -> dict[str, Any]:
    """Create a Stripe Customer Portal session for self-serve management."""
    if not stripe_service.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED)
    try:
        out = stripe_service.create_billing_portal_session(customer_id=body.customer_id)
    except stripe_service.BillingNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    return {"success": True, "data": out}


@router.post("/webhook")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    """Receive and verify Stripe webhooks. Must stay UNAUTHENTICATED (Stripe calls it).

    Path /api/v1/billing/webhook is listed in EXEMPT_PATHS in api/main.py.
    """
    if not stripe_service.is_configured():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, _NOT_CONFIGURED)
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe_service.construct_event(payload, sig)
    except stripe_service.BillingNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    except Exception as exc:  # invalid signature / payload
        logger.warning("billing.webhook_invalid", error=str(exc))
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invalid webhook: {exc}")
    result = await stripe_service.handle_event(event)
    return {"received": True, **result}

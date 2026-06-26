"""integrations/stripe/service.py - Stripe Billing service layer for Owlbell.

Subscription checkout, customer billing portal, and webhook handling for the
managed-service tiers (Basic / Pro / Pro Plus). Enterprise is sold custom and is
not self-serve.

Design notes
------------
- The ``stripe`` package is imported **lazily** inside functions so importing this
  module never fails, even if ``stripe`` isn't installed or no key is set.
- ``is_configured()`` lets callers degrade gracefully (return 503) instead of crashing.
- Plan -> Stripe price IDs are resolved from settings (created by
  ``scripts/stripe_setup.py``).
- Webhooks drive tenant lifecycle: create + activate on payment, suspend on cancel/failure.
- All webhook handlers are async and accept an optional ``db`` session so callers
  (FastAPI routes) can provide one instead of each handler creating its own.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

try:  # dual-import: works whether 'backend' or its parent is on sys.path
    from config import get_settings
except ImportError:  # pragma: no cover
    from backend.config import get_settings  # type: ignore

logger = structlog.get_logger(__name__)


class BillingNotConfigured(RuntimeError):
    """Raised when a Stripe operation is attempted without configuration."""


# --------------------------------------------------------------------------- #
# Managed-service plans (the customer-facing tiers; see gtm/PRICING.md).
# Annual = 10x monthly (2 months free). Setup fee waived on annual.
# --------------------------------------------------------------------------- #
MANAGED_PLANS: dict[str, dict[str, Any]] = {
    "basic": {
        "name": "Basic",
        "monthly_usd": 297,
        "annual_usd": 2970,
        "setup_usd": 500,
        "price_monthly_attr": "stripe_price_basic_monthly",
        "price_annual_attr": "stripe_price_basic_annual",
        "setup_attr": "stripe_price_setup_basic",
        "blurb": "24/7 AI answering, voicemail-to-text, instant alerts. 1 number.",
    },
    "pro": {
        "name": "Pro",
        "monthly_usd": 797,
        "annual_usd": 7970,
        "setup_usd": 1000,
        "price_monthly_attr": "stripe_price_pro_monthly",
        "price_annual_attr": "stripe_price_pro_annual",
        "setup_attr": "stripe_price_setup_pro",
        "blurb": "Full conversations, appointment booking, CRM, routing, analytics.",
    },
    "pro_plus": {
        "name": "Pro Plus",
        "monthly_usd": 1497,
        "annual_usd": 14970,
        "setup_usd": 1000,
        "price_monthly_attr": "stripe_price_pro_plus_monthly",
        "price_annual_attr": "stripe_price_pro_plus_annual",
        "setup_attr": "stripe_price_setup_pro",
        "blurb": "High call volume, extra numbers, priority same-day support.",
    },
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _secret() -> Optional[str]:
    key = get_settings().integrations.stripe_secret_key
    return key.get_secret_value() if key else None


def is_configured() -> bool:
    """True if a Stripe secret key is set (billing can run)."""
    return bool(_secret())


def _client():
    """Return the configured ``stripe`` module, or raise BillingNotConfigured."""
    secret = _secret()
    if not secret:
        raise BillingNotConfigured("Stripe secret key not configured")
    try:
        import stripe  # lazy import
    except ImportError as exc:  # pragma: no cover
        raise BillingNotConfigured("The 'stripe' package is not installed") from exc
    stripe.api_key = secret
    return stripe


def price_id_for(plan: str, period: str) -> Optional[str]:
    """Resolve the Stripe price ID for a plan + period ('monthly'|'annual')."""
    meta = MANAGED_PLANS.get(plan)
    if not meta:
        return None
    attr = meta["price_annual_attr"] if period == "annual" else meta["price_monthly_attr"]
    return getattr(get_settings().integrations, attr, None)


def list_plans() -> list[dict[str, Any]]:
    """Public-safe plan catalog for the pricing UI."""
    out = []
    for plan_id, meta in MANAGED_PLANS.items():
        out.append({
            "id": plan_id,
            "name": meta["name"],
            "monthly_usd": meta["monthly_usd"],
            "annual_usd": meta["annual_usd"],
            "setup_usd": meta["setup_usd"],
            "blurb": meta["blurb"],
            "purchasable": bool(price_id_for(plan_id, "monthly")),
        })
    return out


# --------------------------------------------------------------------------- #
# Checkout & portal
# --------------------------------------------------------------------------- #

def create_checkout_session(
    *,
    plan: str,
    period: str = "monthly",
    customer_email: Optional[str] = None,
    tenant_id: Optional[str] = None,
    include_setup_fee: bool = True,
    success_url: Optional[str] = None,
    cancel_url: Optional[str] = None,
) -> dict[str, Any]:
    """Create a Stripe Checkout Session for a subscription.

    Returns ``{"id": ..., "url": ...}``. Redirect the customer to ``url``.
    """
    stripe = _client()
    settings = get_settings().integrations

    if plan not in MANAGED_PLANS:
        raise ValueError(f"Unknown plan '{plan}'. Choose from {list(MANAGED_PLANS)}.")
    price_id = price_id_for(plan, period)
    if not price_id:
        raise BillingNotConfigured(
            f"No Stripe price configured for {plan}/{period}. Run scripts/stripe_setup.py."
        )

    line_items: list[dict[str, Any]] = [{"price": price_id, "quantity": 1}]

    # One-time setup fee (monthly only — waived on annual), if a price exists.
    if include_setup_fee and period == "monthly":
        setup_price = getattr(settings, MANAGED_PLANS[plan]["setup_attr"], None)
        if setup_price:
            line_items.append({"price": setup_price, "quantity": 1})

    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=line_items,
        customer_email=customer_email,
        allow_promotion_codes=True,
        success_url=success_url or settings.stripe_checkout_success_url,
        cancel_url=cancel_url or settings.stripe_checkout_cancel_url,
        subscription_data={"metadata": {"plan": plan, "tenant_id": tenant_id or ""}},
        metadata={"plan": plan, "tenant_id": tenant_id or ""},
    )
    logger.info("billing.checkout_created", plan=plan, period=period, session_id=session.get("id"))
    return {"id": session.get("id"), "url": session.get("url")}


def create_billing_portal_session(
    *, customer_id: str, return_url: Optional[str] = None
) -> dict[str, Any]:
    """Create a Stripe Customer Portal session (self-serve plan/card management)."""
    stripe = _client()
    settings = get_settings().integrations
    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url or settings.stripe_billing_portal_return_url,
    )
    return {"url": session.get("url")}


# --------------------------------------------------------------------------- #
# Webhook event handling
# --------------------------------------------------------------------------- #

def construct_event(payload: bytes, sig_header: str) -> Any:
    """Verify and parse a Stripe webhook event. Raises on invalid signature."""
    stripe = _client()
    secret = get_settings().integrations.stripe_webhook_secret
    if not secret:
        raise BillingNotConfigured("Stripe webhook secret not configured")
    return stripe.Webhook.construct_event(
        payload=payload, sig_header=sig_header, secret=secret.get_secret_value()
    )


async def handle_event(event: Any, db: Optional[AsyncSession] = None) -> dict[str, Any]:
    """Route a verified webhook event to the right tenant-lifecycle action.

    Accepts an optional ``db`` session. When provided the handler uses it directly;
    otherwise it creates its own session.

    Returns a summary dict ``{"event_type": ..., "action": ...}``.
    """
    etype = event.get("type") if isinstance(event, dict) else getattr(event, "type", "")
    data = (event.get("data", {}) or {}).get("object", {}) if isinstance(event, dict) else {}

    action = "ignored"
    if etype == "checkout.session.completed":
        meta = data.get("metadata", {}) or {}
        await _provision(
            db=db,
            tenant_id=meta.get("tenant_id"),
            plan=meta.get("plan"),
            customer_id=data.get("customer"),
            subscription_id=data.get("subscription"),
            email=(data.get("customer_details") or {}).get("email"),
        )
        action = "provisioned"

        # Send purchase alert to configured email
        await _send_purchase_alert(
            plan=meta.get("plan", "unknown"),
            customer_email=(data.get("customer_details") or {}).get("email", "unknown"),
            amount=(data.get("amount_total") or 0) / 100,
            currency=data.get("currency", "usd"),
        )
    elif etype == "invoice.paid":
        await _mark_active(db=db, customer_id=data.get("customer"))
        action = "marked_active"
    elif etype in ("invoice.payment_failed",):
        await _flag_dunning(db=db, customer_id=data.get("customer"))
        action = "dunning"
    elif etype == "customer.subscription.deleted":
        await _suspend(db=db, customer_id=data.get("customer"))
        action = "suspended"

    logger.info("billing.webhook", event_type=etype, action=action)
    return {"event_type": etype, "action": action}


async def _send_purchase_alert(
    *,
    plan: str,
    customer_email: str,
    amount: float,
    currency: str,
) -> None:
    """Send a Gmail notification about a new Stripe purchase."""
    settings = get_settings().integrations
    alert_email = settings.stripe_purchase_alert_email
    if not alert_email:
        return

    try:
        from backend.integrations.gmail.service import send_email, is_configured

        if not is_configured():
            logger.warning("billing.purchase_alert.gmail_not_configured")
            return

        plan_label = MANAGED_PLANS.get(plan, {}).get("name", plan.capitalize())
        result = await send_email(
            to_email=alert_email,
            to_name="Owlbell Admin",
            subject=f"🎉 New {plan_label} Purchase — ${amount:.2f} {currency.upper()}",
            body_text=(
                f"New Stripe purchase received!\n\n"
                f"Plan: {plan_label}\n"
                f"Customer Email: {customer_email}\n"
                f"Amount: ${amount:.2f} {currency.upper()}\n"
                f"Time: {datetime.now(timezone.utc).isoformat()}\n"
            ),
        )
        if result.get("success"):
            logger.info("billing.purchase_alert.sent", plan=plan, email=customer_email)
        else:
            logger.warning("billing.purchase_alert.failed", error=result.get("error"))
    except Exception as exc:
        logger.error("billing.purchase_alert.error", error=str(exc))


# --------------------------------------------------------------------------- #
# Tenant-lifecycle hooks
# --------------------------------------------------------------------------- #
# Each accepts an optional ``db`` AsyncSession. When provided it is used for
# all DB work; otherwise a new session is created from the session maker.
# This lets FastAPI routes chain work in a single transaction when convenient.

async def _provision(
    *,
    db: Optional[AsyncSession] = None,
    tenant_id: Optional[str],
    plan: Optional[str],
    customer_id: Optional[str],
    subscription_id: Optional[str],
    email: Optional[str],
) -> None:
    """Create or update a tenant subscription after successful checkout.

    For self-serve signup (no pre-created tenant) this creates a new tenant
    with a generated slug and name derived from the customer email.
    """
    from backend.dependencies import get_session_maker
    from backend.db.models.tenant import Tenant
    from backend.db.models.enums import PlanTier, TenantStatus
    from backend.db.models.user import User
    from backend.db.models.enums import UserRole

    plan_map = {"basic": PlanTier.BASIC, "pro": PlanTier.PRO, "pro_plus": PlanTier.PRO_PLUS}
    plan_tier = plan_map.get(plan or "", PlanTier.FREE)

    stripe_config = {
        "stripe_customer_id": customer_id or "",
        "stripe_subscription_id": subscription_id or "",
        "stripe_email": email or "",
    }

    own_session = db is None
    if own_session:
        maker = get_session_maker()
        if not maker:
            logger.error("billing.provision_no_db", tenant_id=tenant_id)
            return
        db = maker()

    try:
        if tenant_id:
            # Existing tenant — update plan + stripe metadata
            await db.execute(
                update(Tenant)
                .where(Tenant.id == tenant_id)
                .values(plan_tier=plan_tier, config_json=stripe_config)
            )
            logger.info("billing.provision_existing", tenant_id=tenant_id, plan=plan)
        else:
            # Self-serve signup — create tenant + admin user
            slug = _generate_slug(email or customer_id or "customer")
            tenant = Tenant(
                slug=slug,
                name=slug.replace("-", " ").title(),
                plan_tier=plan_tier,
                status=TenantStatus.TRIAL,
                business_email=email or "",
                config_json={
                    **stripe_config,
                    "onboarding_step": 1,
                    "onboarding_complete": False,
                    "calls_this_month": 0,
                    "calls_last_month": 0,
                    "revenue_mtd": 0.0,
                },
            )
            db.add(tenant)
            await db.flush()

            user = User(
                email=email or f"{slug}@temp.owlbell.xyz",
                password_hash="",
                first_name="",
                last_name="",
                role=UserRole.ADMIN,
                tenant_id=tenant.id,
                is_active=True,
            )
            db.add(user)
            await db.flush()

            tenant_id = str(tenant.id)
            logger.info("billing.provision_new", tenant_id=tenant_id, plan=plan)

        await db.commit()
    except Exception as exc:
        await db.rollback()
        logger.error("billing.provision_error", error=str(exc), tenant_id=tenant_id)
    finally:
        if own_session:
            await db.close()


async def _mark_active(*, db: Optional[AsyncSession] = None, customer_id: Optional[str]) -> None:
    """Mark tenant as active (clear dunning hold)."""
    from backend.dependencies import get_session_maker
    from backend.db.models.tenant import Tenant
    from backend.db.models.enums import TenantStatus
    if not customer_id:
        return
    own_session = db is None
    if own_session:
        maker = get_session_maker()
        if not maker:
            return
        db = maker()

    try:
        tenant = await _find_by_stripe_customer(db, customer_id)
        if tenant:
            tenant.status = TenantStatus.ACTIVE
            await db.commit()
            logger.info("billing.mark_active_ok", tenant_id=str(tenant.id))
    except Exception as exc:
        await db.rollback()
        logger.error("billing.mark_active_error", error=str(exc))
    finally:
        if own_session:
            await db.close()


async def _flag_dunning(*, db: Optional[AsyncSession] = None, customer_id: Optional[str]) -> None:
    """Flag tenant for dunning (payment failed)."""
    from backend.dependencies import get_session_maker
    from backend.db.models.tenant import Tenant
    from backend.db.models.enums import TenantStatus
    if not customer_id:
        return
    own_session = db is None
    if own_session:
        maker = get_session_maker()
        if not maker:
            return
        db = maker()

    try:
        tenant = await _find_by_stripe_customer(db, customer_id)
        if tenant:
            tenant.status = TenantStatus.SUSPENDED
            await db.commit()
            logger.warning("billing.dunning_flagged", tenant_id=str(tenant.id))
    except Exception as exc:
        await db.rollback()
        logger.error("billing.dunning_error", error=str(exc))
    finally:
        if own_session:
            await db.close()


async def _suspend(*, db: Optional[AsyncSession] = None, customer_id: Optional[str]) -> None:
    """Suspend tenant access."""
    from backend.dependencies import get_session_maker
    from backend.db.models.tenant import Tenant
    from backend.db.models.enums import TenantStatus
    if not customer_id:
        return
    own_session = db is None
    if own_session:
        maker = get_session_maker()
        if not maker:
            return
        db = maker()

    try:
        tenant = await _find_by_stripe_customer(db, customer_id)
        if tenant:
            tenant.status = TenantStatus.SUSPENDED
            await db.commit()
            logger.warning("billing.suspended", tenant_id=str(tenant.id))
    except Exception as exc:
        await db.rollback()
        logger.error("billing.suspend_error", error=str(exc))
    finally:
        if own_session:
            await db.close()


async def _find_by_stripe_customer(db: AsyncSession, customer_id: str) -> Optional[Any]:
    """Find a tenant by ``stripe_customer_id`` in ``config_json``."""
    from backend.db.models.tenant import Tenant
    result = await db.execute(select(Tenant))
    for tenant in result.scalars().all():
        cfg = tenant.config_json or {}
        if cfg.get("stripe_customer_id") == customer_id:
            return tenant
    return None


def _generate_slug(seed: str) -> str:
    """Generate a unique tenant slug from a seed string."""
    safe = "".join(c if c.isalnum() else "-" for c in seed.lower()).strip("-")
    suffix = uuid.uuid4().hex[:8]
    return f"{safe}-{suffix}" if safe else f"client-{suffix}"

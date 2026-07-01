#!/usr/bin/env python3
"""scripts/stripe_setup.py - Create Owlbell's products & prices in Stripe.

Run ONCE per Stripe account (test mode first). It creates a Product per managed
tier (Launch / Growth / Scale) with monthly + annual recurring prices and a
one-time setup-fee price, then prints the env vars to paste into your .env.

Idempotent: it reuses existing products/prices (matched by metadata + nickname)
so re-running won't create duplicates.

Usage:
    export STRIPE_SECRET_KEY=sk_test_xxx        # use a TEST key first!
    python scripts/stripe_setup.py
    # then copy the printed INTEGRATION_STRIPE_PRICE_* lines into your .env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Load .env file automatically
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass  # dotenv not installed, rely on system env vars

try:
    import stripe
except ImportError:
    print("The 'stripe' package is required: pip install stripe", file=sys.stderr)
    raise SystemExit(1)

# Plan catalog mirrors integrations/stripe/service.py MANAGED_PLANS.
PLANS = {
    "basic": {"name": "Owlbell Launch", "monthly": 1497, "annual": 14970, "setup": 2500},
    "pro": {"name": "Owlbell Growth", "monthly": 4997, "annual": 49970, "setup": 5000},
    "pro_plus": {"name": "Owlbell Scale", "monthly": 9997, "annual": 99970, "setup": 10000},
}


def _find_product(plan_key: str):
    for prod in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        try:
            metadata = dict(prod.metadata) if prod.metadata else {}
        except Exception:
            metadata = {}
        if metadata.get("owlbell_plan") == plan_key:
            return prod
    return None


def _find_price(product_id: str, nickname: str):
    for price in stripe.Price.list(product=product_id, active=True, limit=100).auto_paging_iter():
        if getattr(price, "nickname", None) == nickname:
            return price
    return None


def _ensure_product(plan_key: str, name: str):
    prod = _find_product(plan_key)
    if prod:
        print(f"  product exists: {name} ({prod.id})")
        return prod
    prod = stripe.Product.create(name=name, metadata={"owlbell_plan": plan_key})
    print(f"  created product: {name} ({prod.id})")
    return prod


def _ensure_recurring(product_id: str, nickname: str, amount_usd: int, interval: str):
    existing = _find_price(product_id, nickname)
    if existing:
        return existing.id
    price = stripe.Price.create(
        product=product_id,
        unit_amount=amount_usd * 100,
        currency="usd",
        recurring={"interval": interval},
        nickname=nickname,
    )
    return price.id


def _ensure_onetime(product_id: str, nickname: str, amount_usd: int):
    existing = _find_price(product_id, nickname)
    if existing:
        return existing.id
    price = stripe.Price.create(
        product=product_id, unit_amount=amount_usd * 100, currency="usd", nickname=nickname,
    )
    return price.id


def main() -> int:
    secret = os.environ.get("STRIPE_SECRET_KEY") or os.environ.get("INTEGRATION_STRIPE_SECRET_KEY")
    if not secret:
        print("Set STRIPE_SECRET_KEY (use a sk_test_... key first).", file=sys.stderr)
        return 2
    stripe.api_key = secret
    mode = "TEST" if secret.startswith("sk_test_") else "LIVE"
    print(f"Stripe mode: {mode}\n")

    env_lines: list[str] = []
    setup_ids: dict[str, str] = {}

    for key, p in PLANS.items():
        print(f"{p['name']}:")
        prod = _ensure_product(key, p["name"])
        monthly = _ensure_recurring(prod.id, f"{key}_monthly", p["monthly"], "month")
        annual = _ensure_recurring(prod.id, f"{key}_annual", p["annual"], "year")
        setup = _ensure_onetime(prod.id, f"{key}_setup", p["setup"])
        setup_ids[key] = setup
        env_lines.append(f"INTEGRATION_STRIPE_PRICE_{key.upper()}_MONTHLY={monthly}")
        env_lines.append(f"INTEGRATION_STRIPE_PRICE_{key.upper()}_ANNUAL={annual}")
        print(f"  monthly={monthly}  annual={annual}  setup={setup}")

    # Setup-fee price IDs
    print("\n# ---- paste these into your .env ----")
    for line in env_lines:
        print(line)
    for key, sid in setup_ids.items():
        print(f"INTEGRATION_STRIPE_PRICE_SETUP_{key.upper()}={sid}")
    print("\nNext: set INTEGRATION_STRIPE_WEBHOOK_SECRET from your webhook endpoint, "
          "then point Stripe at POST /api/v1/billing/webhook.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Test Harness — Simulate a Stripe Checkout End-to-End

Simulates a Stripe "checkout.session.completed" webhook event and sends it
to the n8n webhook trigger URL, then optionally validates each downstream
step against the Retell API.

Usage:
    # Send webhook to your running n8n instance:
    python n8n/test-harness.py send --webhook-url http://localhost:5678/webhook/stripe-checkout-completed

    # Run a local simulation (calls Retell API directly, no n8n):
    python n8n/test-harness.py simulate --retell-api-key key_xxx

    # Run both in sequence:
    python n8n/test-harness.py all --webhook-url ... --retell-api-key ...
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Fixture: realistic Stripe checkout.session.completed payload
# ---------------------------------------------------------------------------

def build_stripe_webhook(overrides: dict = None) -> dict:
    """Build a realistic Stripe checkout.session.completed webhook payload."""

    session_id = "cs_test_" + uuid.uuid4().hex[:24]

    payload = {
        "id": f"evt_{uuid.uuid4().hex[:24]}",
        "object": "event",
        "api_version": "2023-10-16",
        "created": int(time.time()),
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "object": "checkout.session",
                "after_expiration": None,
                "allow_promotion_codes": None,
                "amount_subtotal": 9999,
                "amount_total": 9999,
                "automatic_tax": {"enabled": False, "status": None},
                "billing_address_collection": None,
                "cancel_url": "https://app.owlbell.xyz/billing?status=cancelled",
                "client_reference_id": None,
                "consent": None,
                "consent_collection": None,
                "created": int(time.time()),
                "currency": "usd",
                "currency_conversion": None,
                "custom_fields": [],
                "custom_text": {"after_submit": None, "shipping_address": None, "submit": None},
                "customer": None,
                "customer_creation": "if_required",
                "customer_details": {
                    "email": "jane@example.com",
                    "phone": None,
                    "tax_exempt": "none",
                    "tax_ids": [],
                },
                "customer_email": "jane@example.com",
                "expires_at": int(time.time()) + 3600,
                "invoice": None,
                "invoice_creation": {"enabled": False, "invoice_data": {"account_tax_ids": None, "custom_fields": None, "description": None, "footer": None, "issuer": None, "metadata": {}, "rendering_options": None}},
                "livemode": False,
                "locale": None,
                "metadata": {
                    "business_name": "Smith's HVAC & Plumbing",
                    "email": "jane@example.com",
                    "phone": "+12125551234",
                    "business_hours": "Monday to Friday, 7 AM to 7 PM; Saturday, 8 AM to 4 PM",
                    "services": "HVAC repair, plumbing, electrical, roofing, drain cleaning",
                    "pricing_info": "Free estimates. $75 diagnostic fee waived with any repair.",
                    "booking_link": "https://smithshvac.com/book",
                    "business_address": "123 Oak Street, Springfield, IL 62701",
                    "transfer_number": "+12125551234",
                    "area_code": "217",
                    "faq_emergency_contacts": "For gas leaks, call 911 immediately. For burst pipes, call our 24/7 emergency line at +12125559876.",
                    "plan": "pro_monthly",
                },
                "mode": "subscription",
                "payment_intent": None,
                "payment_link": None,
                "payment_method_collection": "if_required",
                "payment_method_configuration_details": None,
                "payment_method_options": {},
                "payment_method_types": ["card"],
                "payment_status": "paid",
                "phone_number_collection": {"enabled": False},
                "recovered_from": None,
                "setup_intent": None,
                "shipping": None,
                "shipping_address_collection": None,
                "shipping_cost": None,
                "shipping_details": None,
                "shipping_options": [],
                "status": "complete",
                "submit_type": None,
                "subscription": f"sub_{uuid.uuid4().hex[:24]}",
                "success_url": "https://app.owlbell.xyz/billing?status=success",
                "total_details": {"amount_discount": 0, "amount_shipping": 0, "amount_tax": 0},
                "ui_mode": "hosted",
                "url": None,
            }
        },
    }

    if overrides:
        _deep_merge(payload, overrides)

    return payload


def _deep_merge(base: dict, overrides: dict):
    """Merge overrides into base, recursing into nested dicts."""
    for k, v in overrides.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_send(args):
    """Send the simulated webhook to n8n."""
    payload = build_stripe_webhook()
    print(f"Sending webhook to {args.webhook_url}...")
    print(f"  Session ID: {payload['data']['object']['id']}")
    print(f"  Business:   {payload['data']['object']['metadata']['business_name']}")
    print(f"  Customer:   {payload['data']['object']['metadata']['email']}")
    print()

    resp = requests.post(
        args.webhook_url,
        json=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=" + str(int(time.time())) + ",v1=fake_signature_for_testing",
            "User-Agent": "Stripe/1.0 (+https://stripe.com)",
        },
        timeout=30,
    )

    print(f"Response: {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  Body: {resp.text[:500]}")
    else:
        try:
            data = resp.json()
            print(f"  Body: {json.dumps(data, indent=2)[:1000]}")
        except Exception:
            print(f"  Body: {resp.text[:200]}")

    return resp


def cmd_simulate(args):
    """Full end-to-end simulation — calls Retell API directly.

    This bypasses n8n entirely and simulates each step the workflow would do.
    Useful for testing the Retell API integration independently.
    """
    from retell import Retell

    client = Retell(api_key=args.retell_api_key)

    # 1. Build intake data (same as the n8n "Parse & Validate" code node)
    payload = build_stripe_webhook()
    meta = payload["data"]["object"]["metadata"]
    session_id = payload["data"]["object"]["id"]

    print("=" * 60)
    print("SIMULATED PROVISIONING")
    print("=" * 60)
    print(f"Session:    {session_id}")
    print(f"Business:   {meta['business_name']}")
    print(f"Email:      {meta['email']}")
    print(f"Phone:      {meta['phone']}")
    print()

    # 2. Create Knowledge Base
    print("--- Step 1: Create Knowledge Base ---")
    kb_texts = [
        {"title": "Business Hours", "text": f"Our business hours are {meta['business_hours']}. We are closed on major holidays."},
        {"title": "Services Offered", "text": f"We offer: {meta['services']}. Free estimates available."},
        {"title": "Pricing and Estimates", "text": f"{meta['pricing_info']} We accept credit cards, cash, and financing."},
        {"title": "Scheduling and Booking", "text": f"Book at {meta['booking_link']} or call {meta['phone']}. We schedule within 24-48 hours."},
        {"title": "Service Area", "text": f"We serve the local area around {meta['business_address']}. Call to confirm coverage."},
        {"title": "Emergency Service", "text": f"{meta['faq_emergency_contacts']} Same-day service available for urgent needs."},
        {"title": "Cancellation Policy", "text": "24-hour notice required. Late cancellations may incur a fee."},
    ]

    try:
        kb = client.knowledge_base.create(
            knowledge_base_name=f"{meta['business_name']} FAQ",
            knowledge_base_texts=kb_texts,
        )
        kb_id = kb.knowledge_base_id
        print(f"  KB ID: {kb_id}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 3. Create LLM
    print("--- Step 2: Create Retell LLM ---")
    webhook_url = args.webhook_base or "https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell"
    tools_secret = os.environ.get("RETELL_AGENT_TOOLS_SECRET", "")
    tool_base = args.tool_base or "https://owlbell-api-production.up.railway.app/api/v1/agent/tools"

    general_prompt = f"""You are a warm, professional AI receptionist for {meta['business_name']}, a home-services company...

[PROMPT TRUNCATED FOR TEST — see n8n workflow for full version]
"""

    try:
        llm = client.llm.create(
            general_prompt=general_prompt,
            general_tools=[
                {
                    "type": "transfer_call",
                    "name": "transfer_to_human",
                    "description": "Transfer to a human team member.",
                    "transfer_destination": {"type": "predefined", "number": meta["phone"]},
                    "transfer_option": {"type": "cold_transfer"},
                    "speak_during_execution": True,
                    "execution_message_description": "Say you're transferring them to a team member.",
                },
                {
                    "type": "end_call",
                    "name": "end_call",
                    "description": "End the call.",
                    "speak_during_execution": True,
                    "execution_message_description": "Say a friendly goodbye.",
                },
            ],
            start_speaker="agent",
            begin_message=f"Hi, you've reached {meta['business_name']}! I'm an AI assistant, and this call may be recorded. How can I help you today?",
            model="gpt-4.1-mini",
            model_temperature=0.4,
        )
        llm_id = llm.llm_id
        print(f"  LLM ID: {llm_id}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 4. Attach KB to LLM
    print("--- Step 3: Attach KB to LLM ---")
    try:
        client.llm.update(llm_id=llm_id, knowledge_base_ids=[kb_id])
        print(f"  KB {kb_id} attached to LLM {llm_id}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 5. Create Agent
    print("--- Step 4: Create Agent ---")
    try:
        agent = client.agent.create(
            agent_name=f"{meta['business_name']} Receptionist",
            response_engine={"type": "retell-llm", "llm_id": llm_id},
            voice_id="retell-Willa",
            webhook_url=webhook_url,
            webhook_events=["call_started", "call_ended", "call_analyzed"],
            language="en-US",
            enable_backchannel=True,
            interruption_sensitivity=0.7,
            responsiveness=0.8,
            end_call_after_silence_ms=30000,
            max_call_duration_ms=1800000,
        )
        agent_id = agent.agent_id
        print(f"  Agent ID: {agent_id}")
    except Exception as e:
        print(f"  FAILED: {e}")
        return False

    # 6. Create Phone Number
    print("--- Step 5: Create Phone Number ---")
    try:
        phone = client.phone_number.create(
            agent_id=agent_id,
            area_code=meta.get("area_code", "555"),
        )
        phone_number = phone.phone_number
        print(f"  Phone: {phone_number}")
    except Exception as e:
        print(f"  FAILED: {e}")
        # Non-fatal — agent still works with existing number
        phone_number = "FAILED (non-fatal)"

    # 7. Publish Agent
    print("--- Step 6: Publish Agent ---")
    try:
        client.agent.update(agent_id=agent_id, is_published=True)
        print(f"  Agent {agent_id} published")
    except Exception as e:
        err_str = str(e).lower()
        if "published" in err_str or "cannot update" in err_str:
            print(f"  (already published — drafting from published version): {e}")
        else:
            print(f"  FAILED: {e}")
            return False

    # 8. Summary
    print()
    print("=" * 60)
    print("PROVISIONING COMPLETE")
    print("=" * 60)
    print(f"  Business:   {meta['business_name']}")
    print(f"  Agent ID:   {agent_id}")
    print(f"  Phone:      {phone_number}")
    print(f"  Webhook:    {webhook_url}")
    print()
    print("Welcome email would be sent to:  {meta['email']}")
    print("Welcome SMS would be sent to:    {meta['phone']}")
    print()

    return True


def cmd_all(args):
    """Send webhook + simulate (no n8n dependency for simulate)."""
    if args.webhook_url:
        cmd_send(args)
        print()
    if args.retell_api_key:
        cmd_simulate(args)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Test harness for Owlbell n8n auto-provisioning workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # send
    p = sub.add_parser("send", help="Send simulated webhook to n8n")
    p.add_argument("--webhook-url", default="http://localhost:5678/webhook/stripe-checkout-completed",
                    help="n8n webhook URL")

    # simulate
    p = sub.add_parser("simulate", help="Simulate full provisioning via Retell API (no n8n)")
    p.add_argument("--retell-api-key", default=os.environ.get("INTEGRATION_RETELL_API_KEY"),
                    help="Retell API key (default: $INTEGRATION_RETELL_API_KEY)")
    p.add_argument("--webhook-base", default="https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell",
                    help="Owlbell webhook URL for the agent")
    p.add_argument("--tool-base", default="https://owlbell-api-production.up.railway.app/api/v1/agent/tools",
                    help="Owlbell tool endpoints base URL")
    p.add_argument("--tools-secret", default=os.environ.get("INTEGRATION_RETELL_AGENT_TOOLS_SECRET"),
                    help="Agent tools auth secret")

    # all
    p = sub.add_parser("all", help="Run send + simulate")
    p.add_argument("--webhook-url", help="n8n webhook URL (optional)")
    p.add_argument("--retell-api-key", default=os.environ.get("INTEGRATION_RETELL_API_KEY"))
    p.add_argument("--webhook-base", default="https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell")
    p.add_argument("--tool-base", default="https://owlbell-api-production.up.railway.app/api/v1/agent/tools")
    p.add_argument("--tools-secret", default=os.environ.get("INTEGRATION_RETELL_AGENT_TOOLS_SECRET"))

    args = parser.parse_args()

    if args.command == "send":
        cmd_send(args)
    elif args.command == "simulate":
        if not args.retell_api_key:
            print("FATAL: --retell-api-key required (or set INTEGRATION_RETELL_API_KEY)")
            sys.exit(1)
        os.environ["RETELL_AGENT_TOOLS_SECRET"] = args.tools_secret or ""
        cmd_simulate(args)
    elif args.command == "all":
        cmd_all(args)


if __name__ == "__main__":
    main()

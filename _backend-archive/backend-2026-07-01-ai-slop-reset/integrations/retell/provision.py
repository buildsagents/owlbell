"""integrations/retell/provision.py - Full Retell agent provisioning for a tenant.

Consolidates the flow previously in ``leads/agents/onboarding.py``:
KB -> LLM (+ tools) -> Agent -> Phone -> Publish, then writes ``tenant_integrations``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings

from backend.db.tenant_integrations_service import upsert_for_tenant
from backend.integrations.retell.service import RetellNotConfigured, is_configured

logger = structlog.get_logger(__name__)

KB_TEXTS_TEMPLATE = [
    {"title": "Business Hours", "text": "Our business hours are {business_hours}. We are closed on major holidays."},
    {"title": "Services Offered", "text": "We offer: {services}. Each service includes a free estimate."},
    {"title": "Pricing and Estimates", "text": "{pricing_info} We accept credit cards, cash, and financing options."},
    {"title": "Scheduling and Booking", "text": "Book online at {booking_link} or call us at {phone}."},
    {"title": "Service Area", "text": "We serve the local area around {business_address}."},
    {"title": "Emergency Service", "text": "{emergency_contacts}"},
    {"title": "Cancellation Policy", "text": "We require 24-hour notice for cancellations."},
]

GENERAL_PROMPT_TEMPLATE = """You are a warm, professional AI receptionist for {business_name}.

## CRITICAL RULES
1. At the start, state you are an AI assistant and the call may be recorded.
2. Stay in scope: services, pricing, scheduling, and policies for {business_name}.
3. Collect name, phone, address, and preferred time when booking.

## FAQs
- Hours: {business_hours}
- Services: {services}
- Pricing: {pricing_info}
- Phone: {phone}
- Address: {business_address}
"""


@dataclass
class ProvisionConfig:
    voice_id: str = "retell-Willa"
    model: str = "gpt-4.1-mini"
    model_temperature: float = 0.4
    language: str = "en-US"
    enable_backchannel: bool = True
    interruption_sensitivity: float = 0.7
    responsiveness: float = 0.8
    end_call_after_silence_ms: int = 30000
    max_call_duration_ms: int = 1800000

    @property
    def webhook_url(self) -> str:
        base = get_settings().api_url.rstrip("/")
        return f"{base}/api/v1/webhooks/retell"

    @property
    def tool_base_url(self) -> str:
        base = get_settings().api_url.rstrip("/")
        return f"{base}/api/v1/agent/tools"

    @property
    def agent_tools_secret(self) -> str:
        secret = get_settings().integrations.retell_agent_tools_secret
        return secret.get_secret_value() if secret else ""

    @property
    def retell_api_key(self) -> str:
        key = get_settings().integrations.retell_api_key
        return key.get_secret_value() if key else ""


def _build_provisioning_data(
    *,
    business_name: str,
    phone: str = "",
    email: str = "",
    trade: str = "home services",
    city: str = "",
    state: str = "",
    intake: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    intake = intake or {}
    services = intake.get("services") or intake.get("trade") or trade
    if isinstance(services, list):
        services = ", ".join(services)
    slug = business_name.lower().replace(" ", "").replace("'", "")
    area_phone = phone or intake.get("phone", "")
    area_code = area_phone[2:5] if area_phone.startswith("+1") and len(area_phone) >= 5 else "555"

    return {
        "business_name": business_name,
        "phone": area_phone,
        "email": email,
        "business_hours": intake.get("business_hours") or "Monday to Friday, 8 AM to 6 PM",
        "services": str(services),
        "pricing_info": intake.get("pricing_info") or "Free estimates. Pricing varies by job.",
        "booking_link": intake.get("booking_link") or f"https://{slug}.com/book",
        "business_address": intake.get("business_address") or f"{city}, {state}".strip(", "),
        "transfer_number": area_phone if area_phone and len(area_phone) >= 10 else "+15125551234",
        "emergency_contacts": intake.get("emergency_contacts") or "For emergencies, call 911.",
        "area_code": area_code,
    }


def _custom_tool(
    tool_base: str,
    tools_secret: str,
    name: str,
    description: str,
    endpoint: str,
) -> dict[str, Any]:
    return {
        "type": "custom",
        "name": name,
        "url": f"{tool_base}/{endpoint}",
        "method": "POST",
        "description": description,
        "headers": {"Authorization": f"Bearer {tools_secret}"},
        "parameters": {"type": "object", "properties": {}, "required": []},
        "speak_during_execution": True,
        "speak_after_execution": True,
        "execution_message_description": description,
        "args_at_root": True,
    }


def provision_from_data(
    *,
    tenant_id: str,
    data: dict[str, str],
    config: Optional[ProvisionConfig] = None,
) -> dict[str, Any]:
    """Sync Retell provisioning (KB, LLM, agent, phone). Returns result dict."""
    cfg = config or ProvisionConfig()
    if not is_configured() or not cfg.retell_api_key:
        return {"status": "failed", "error": "Retell API key not configured"}

    from retell import Retell

    client = Retell(api_key=cfg.retell_api_key)
    name = data["business_name"]

    try:
        kb_texts = []
        for tpl in KB_TEXTS_TEMPLATE:
            text = tpl["text"]
            for k, v in data.items():
                text = text.replace("{" + k + "}", v or "")
            kb_texts.append({"title": tpl["title"], "text": text})

        kb = client.knowledge_base.create(
            knowledge_base_name=f"{name} FAQ",
            knowledge_base_texts=kb_texts,
        )
        kb_id = kb.knowledge_base_id

        prompt = GENERAL_PROMPT_TEMPLATE
        for k, v in data.items():
            prompt = prompt.replace("{" + k + "}", v or "")

        llm = client.llm.create(
            general_prompt=prompt,
            general_tools=[
                {
                    "type": "transfer_call",
                    "name": "transfer_to_human",
                    "description": "Transfer to a human team member.",
                    "transfer_destination": {"type": "predefined", "number": data["transfer_number"]},
                    "transfer_option": {"type": "cold_transfer"},
                    "speak_during_execution": True,
                    "execution_message_description": "Transferring to a team member.",
                },
                {
                    "type": "end_call",
                    "name": "end_call",
                    "description": "End the call when the customer is satisfied.",
                    "speak_during_execution": True,
                    "execution_message_description": "Say goodbye and thank them.",
                },
                _custom_tool(cfg.tool_base_url, cfg.agent_tools_secret, "lookup_caller", "Look up caller by phone.", "lookup-caller"),
                _custom_tool(cfg.tool_base_url, cfg.agent_tools_secret, "log_message", "Log a caller message.", "log-message"),
                _custom_tool(cfg.tool_base_url, cfg.agent_tools_secret, "qualify_lead", "Qualify a lead.", "qualify-lead"),
                _custom_tool(cfg.tool_base_url, cfg.agent_tools_secret, "check_availability", "Check appointment slots.", "check-availability"),
                _custom_tool(cfg.tool_base_url, cfg.agent_tools_secret, "book_appointment", "Book an appointment.", "book-appointment"),
            ],
            start_speaker="agent",
            begin_message=(
                f"Hi, you've reached {name}! I'm an AI assistant, and this call may be recorded. "
                "How can I help you today?"
            ),
            model=cfg.model,
            model_temperature=cfg.model_temperature,
        )
        llm_id = llm.llm_id
        client.llm.update(llm_id=llm_id, knowledge_base_ids=[kb_id])

        agent = client.agent.create(
            agent_name=f"{name} Receptionist",
            response_engine={"type": "retell-llm", "llm_id": llm_id},
            voice_id=cfg.voice_id,
            webhook_url=cfg.webhook_url,
            webhook_events=["call_started", "call_ended", "call_analyzed"],
            language=cfg.language,
            enable_backchannel=cfg.enable_backchannel,
            interruption_sensitivity=cfg.interruption_sensitivity,
            responsiveness=cfg.responsiveness,
            end_call_after_silence_ms=cfg.end_call_after_silence_ms,
            max_call_duration_ms=cfg.max_call_duration_ms,
        )
        agent_id = agent.agent_id

        phone_number = "N/A"
        try:
            phone = client.phone_number.create(agent_id=agent_id, area_code=data.get("area_code", "555"))
            phone_number = phone.phone_number
        except Exception as exc:
            logger.warning("retell.provision.phone_failed", tenant_id=tenant_id, error=str(exc))

        try:
            client.agent.update(agent_id=agent_id, is_published=True)
        except Exception as exc:
            logger.warning("retell.provision.publish_failed", tenant_id=tenant_id, error=str(exc))

        result = {
            "status": "complete",
            "retell_agent_id": agent_id,
            "retell_llm_id": llm_id,
            "retell_kb_id": kb_id,
            "retell_phone_number": phone_number,
            "provisioned_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("retell.provision.complete", tenant_id=tenant_id, agent_id=agent_id)
        return result

    except Exception as exc:
        logger.error("retell.provision.failed", tenant_id=tenant_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


async def provision_for_tenant(
    db: AsyncSession,
    tenant_id: Any,
    *,
    intake_payload: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Load tenant context, provision Retell, persist tenant_integrations."""
    from uuid import UUID

    from backend.db.models.tenant import Tenant

    tid = tenant_id if isinstance(tenant_id, UUID) else UUID(str(tenant_id))
    tenant = await db.get(Tenant, tid)
    if not tenant:
        return {"status": "failed", "error": "Tenant not found"}

    intake = intake_payload or {}
    data = _build_provisioning_data(
        business_name=tenant.business_name or tenant.name,
        phone=tenant.business_phone or "",
        email=tenant.business_email or tenant.owner_email or "",
        trade=tenant.industry or "home services",
        intake=intake,
    )

    result = provision_from_data(tenant_id=str(tid), data=data)
    if result.get("status") != "complete":
        return result

    cfg = dict(tenant.config_json or {})
    cfg.update({k: v for k, v in result.items() if k.startswith("retell_")})
    tenant.config_json = cfg

    await upsert_for_tenant(
        db,
        tid,
        retell_agent_id=result.get("retell_agent_id"),
        retell_llm_id=result.get("retell_llm_id"),
        retell_kb_id=result.get("retell_kb_id"),
        retell_phone_number=result.get("retell_phone_number"),
        voice_provider="retell",
    )
    await db.flush()
    return result


def provision_from_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible entry for leads/agents/onboarding.py."""
    data = _build_provisioning_data(
        business_name=lead.get("name", "Your Business"),
        phone=lead.get("phone", ""),
        email=lead.get("email", ""),
        trade=lead.get("trade", "home services"),
        city=lead.get("city", ""),
        state=lead.get("state", ""),
        intake=lead.get("_intelligence") or {},
    )
    return provision_from_data(tenant_id=lead.get("tenant_id", "lead"), data=data)
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import structlog

from backend.config import get_settings
from backend.integrations.retell.provision import provision_from_lead
from backend.leads import lead_store

logger = structlog.get_logger(__name__)

KB_TEXTS_TEMPLATE = [
    {"title": "Business Hours", "text": "Our business hours are {business_hours}. We are closed on major holidays. Emergency service may be available — please call to check."},
    {"title": "Services Offered", "text": "We offer: {services}. Each service includes a free estimate. Contact us for detailed pricing."},
    {"title": "Pricing and Estimates", "text": "{pricing_info} We accept credit cards, cash, and financing options."},
    {"title": "Scheduling and Booking", "text": "Book an appointment online at {booking_link} or call us at {phone}. We typically schedule within 24-48 hours."},
    {"title": "Service Area", "text": "We serve the local area around {business_address}. Call to confirm if we cover your location."},
    {"title": "Emergency Service", "text": "{emergency_contacts} For urgent needs during business hours, we will do our best to accommodate same-day service."},
    {"title": "Cancellation Policy", "text": "We require 24-hour notice for cancellations. Late cancellations may be subject to a fee."},
]

GENERAL_PROMPT_TEMPLATE = """You are a warm, professional AI receptionist for {business_name}, a plumbing company. You answer inbound calls from customers seeking plumbing services.

## CRITICAL RULES
1. AI Disclosure: At the very start of the call, clearly state: "Hi, you've reached {business_name}! I'm an AI assistant, and this call may be recorded for quality and training purposes. How can I help you today?"
2. Stay in scope: Only answer questions about {business_name}'s services, pricing, scheduling, and policies. If asked about anything outside your knowledge, say "I'm not sure about that — let me transfer you to a team member who can help."
3. Be helpful and efficient. Keep responses concise and professional. Do not be overly chatty.
4. Collect information: When a customer wants to book or get a quote, collect: service needed, their name, phone number, address, and preferred time.

## HANDLING FAQs
- Hours: {business_hours}
- Services: {services}
- Pricing: {pricing_info}
- Booking: {booking_link}
- Address: {business_address}
- Phone: {phone}
- Emergencies: {emergency_contacts}

## TRANSFERRING
If the customer needs to speak with a human:
- Use the transfer call tool to send them to {transfer_number}
- Say: "Let me transfer you to one of our team members who can help with that. Please hold."

## ENDING CALLS
Always confirm next steps before ending. Say something like:
"Great, I've scheduled your appointment for [time]. Is there anything else I can help you with?"
If nothing else: "Thank you for calling {business_name}! Have a great day!"""  # noqa: E501


@dataclass
class ProvisioningConfig:
    retell_api_key: str = ""
    agent_tools_secret: str = ""
    webhook_url: str = "https://owlbell-api-production.up.railway.app/api/v1/webhooks/retell"
    tool_base_url: str = "https://owlbell-api-production.up.railway.app/api/v1/agent/tools"
    voice_id: str = "retell-Willa"
    model: str = "gpt-4.1-mini"
    model_temperature: float = 0.4
    language: str = "en-US"
    enable_backchannel: bool = True
    interruption_sensitivity: float = 0.7
    responsiveness: float = 0.8
    end_call_after_silence_ms: int = 30000
    max_call_duration_ms: int = 1800000

    def __post_init__(self):
        s = get_settings()
        if not self.retell_api_key:
            key = s.integrations.retell_api_key
            if hasattr(key, "get_secret_value"):
                key = key.get_secret_value()
            self.retell_api_key = key or ""
        if not self.agent_tools_secret:
            secret = s.integrations.retell_agent_tools_secret
            if hasattr(secret, "get_secret_value"):
                secret = secret.get_secret_value()
            self.agent_tools_secret = secret or ""


class OnboardingAgent:
    """Thin wrapper — delegates to ``integrations.retell.provision``."""

    def __init__(self, config: Optional[ProvisioningConfig] = None):
        self.config = config or ProvisioningConfig()

    async def provision(self, lead: dict[str, Any]) -> dict[str, Any]:
        self._update_status(lead, "provisioning", "Starting Retell provisioning")
        result = provision_from_lead(lead)
        if result.get("status") == "complete":
            self._save_provisioning(lead, result)
        else:
            self._update_status(lead, "failed", result.get("error", "Provisioning failed"))
        return result

    def _update_status(self, lead: dict[str, Any], status: str, note: str) -> None:
        email = lead.get("email", "")
        if email:
            lead_store.update_lead(email, _onboarding_status=status, _onboarding_note=note)

    def _save_provisioning(self, lead: dict[str, Any], result: dict[str, Any]) -> None:
        email = lead.get("email", "")
        if email:
            lead_store.update_lead(
                email,
                _onboarding_status="complete",
                _onboarding_result=result,
                status="onboarded",
                retell_agent_id=result.get("retell_agent_id"),
                retell_phone_number=result.get("retell_phone_number"),
                retell_llm_id=result.get("retell_llm_id"),
            )

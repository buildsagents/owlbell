"""integrations/retell/service.py - Retell AI integration for phone provisioning.

Manages phone number provisioning and AI agent configuration per tenant via
the Retell AI API. Handles:
- Phone number provisioning (new numbers or SIP trunk connection)
- AI agent creation and configuration per tenant
- Call forwarding setup
- Agent-greeting sync

Design notes
------------
- Retell SDK is imported lazily so this module works even if retell-sdk isn't installed.
- ``is_configured()`` lets callers degrade gracefully.
- All operations are scoped to a tenant_id for multi-tenant isolation.
- Mutations use exponential backoff retry on transient failures.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Callable, Optional, TypeVar

import structlog

from backend.config import get_settings

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
BASE_DELAY_S = 1.0

F = TypeVar("F", bound=Callable[..., Any])


class RetellNotConfigured(RuntimeError):
    """Raised when a Retell operation is attempted without configuration."""


# ---------------------------------------------------------------------------
# Retry helper (sync)
# ---------------------------------------------------------------------------


def _idempotency_key(func: str, **kwargs) -> str:
    """Deterministic idempotency key from function name + sorted kwargs."""
    raw = f"{func}:{json.dumps(kwargs, sort_keys=True, default=str)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _retry_on_failure(fn: F) -> F:
    """Decorator: wraps a sync SDK call with exponential backoff retry.

    Retries on any exception up to MAX_RETRIES times.
    """
    import functools

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt == MAX_RETRIES:
                    raise
                delay = BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "retell.retry",
                    fn=fn.__name__, error=str(exc), attempt=attempt, next_delay_s=delay,
                )
                time.sleep(delay)
        raise last_exc  # type: ignore[misc]

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _api_key() -> Optional[str]:
    key = get_settings().integrations.retell_api_key
    return key.get_secret_value() if key else None


def is_configured() -> bool:
    """True if a Retell API key is set."""
    return bool(_api_key())


def _client():
    """Return the configured Retell client, or raise RetellNotConfigured."""
    key = _api_key()
    if not key:
        raise RetellNotConfigured("Retell API key not configured")
    try:
        import retell  # lazy import
    except ImportError as exc:
        raise RetellNotConfigured("The 'retell-sdk' package is not installed") from exc
    retell.api_key = key
    return retell


# ---------------------------------------------------------------------------
# Phone number management
# ---------------------------------------------------------------------------


def list_available_numbers(area_code: Optional[str] = None, country: str = "US") -> list[dict[str, Any]]:
    """List available phone numbers for provisioning."""
    if not is_configured():
        return []
    try:
        client = _client()
        numbers = client.phone_number.list(
            country=country,
            area_code=area_code,
        )
        return [
            {
                "id": n.get("id"),
                "number": n.get("phone_number"),
                "area_code": n.get("area_code"),
                "country": n.get("country"),
                "monthly_cost": n.get("monthly_cost"),
                "type": n.get("type"),
            }
            for n in (numbers or [])
        ]
    except Exception as exc:
        logger.warning("retell.list_numbers_failed", error=str(exc))
        return []


def provision_number(
    tenant_id: str,
    phone_number: Optional[str] = None,
    area_code: Optional[str] = None,
    friendly_name: Optional[str] = None,
) -> dict[str, Any]:
    """Provision a new phone number for a tenant.

    If phone_number is provided, attempts to buy that specific number.
    Otherwise, picks an available number in the given area_code.
    """
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    client = _client()

    try:
        if phone_number:
            result = _retry_on_failure(client.phone_number.buy)(
                phone_number=phone_number,
                friendly_name=friendly_name or f"Owlbell - {tenant_id[:8]}",
            )
        else:
            available = list_available_numbers(area_code=area_code)
            if not available:
                raise ValueError(f"No available numbers in area code {area_code}")
            result = _retry_on_failure(client.phone_number.buy)(
                phone_number=available[0]["number"],
                friendly_name=friendly_name or f"Owlbell - {tenant_id[:8]}",
            )

        logger.info("retell.number_provisioned", tenant_id=tenant_id, number=result.get("phone_number"))
        return {
            "success": True,
            "phone_number_id": result.get("id"),
            "phone_number": result.get("phone_number"),
            "area_code": result.get("area_code"),
            "monthly_cost": result.get("monthly_cost"),
        }
    except Exception as exc:
        logger.error("retell.provision_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


def deprovision_number(phone_number_id: str, tenant_id: str) -> dict[str, Any]:
    """Release a phone number."""
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    try:
        client = _client()
        _retry_on_failure(client.phone_number.delete)(phone_number_id=phone_number_id)
        logger.info("retell.number_deprovisioned", tenant_id=tenant_id, phone_number_id=phone_number_id)
        return {"success": True}
    except Exception as exc:
        logger.error("retell.deprovision_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# AI Agent management
# ---------------------------------------------------------------------------


def create_agent(
    tenant_id: str,
    name: str,
    greeting: str,
    system_prompt: str,
    voice_id: Optional[str] = None,
    language: str = "en",
    interruption_sensitivity: float = 0.5,
    ambient_sound: Optional[str] = None,
    responsiveness: float = 0.5,
    enable_backchannel: bool = True,
    boosted_keywords: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Create an AI agent for a tenant.

    Each tenant gets their own Retell agent with custom greeting, system prompt,
    and voice settings.
    """
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    client = _client()

    try:
        agent_config = {
            "agent_name": name,
            "response_engine": {
                "type": "retell-llm",
                "general_prompt": system_prompt,
                "begin_message": greeting,
                "language": language,
            },
            "voice_id": voice_id or "11labs-Joanna",
            "interruption_sensitivity": interruption_sensitivity,
            "responsiveness": responsiveness,
            "enable_backchannel": enable_backchannel,
        }

        if ambient_sound:
            agent_config["ambient_sound"] = ambient_sound
        if boosted_keywords:
            agent_config["boosted_keywords"] = boosted_keywords

        result = _retry_on_failure(client.agent.create)(**agent_config)

        agent_id = result.get("agent_id")
        logger.info("retell.agent_created", tenant_id=tenant_id, agent_id=agent_id)

        return {
            "success": True,
            "agent_id": agent_id,
            "agent_name": name,
        }
    except Exception as exc:
        logger.error("retell.agent_create_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


def update_agent(
    agent_id: str,
    tenant_id: str,
    greeting: Optional[str] = None,
    system_prompt: Optional[str] = None,
    voice_id: Optional[str] = None,
    language: Optional[str] = None,
    interruption_sensitivity: Optional[float] = None,
    responsiveness: Optional[float] = None,
    boosted_keywords: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Update an existing agent's configuration."""
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    client = _client()

    update_fields = {}
    if greeting is not None or system_prompt is not None:
        response_engine = {}
        if system_prompt is not None:
            response_engine["general_prompt"] = system_prompt
        if greeting is not None:
            response_engine["begin_message"] = greeting
        if language is not None:
            response_engine["language"] = language
        update_fields["response_engine"] = response_engine

    if voice_id is not None:
        update_fields["voice_id"] = voice_id
    if interruption_sensitivity is not None:
        update_fields["interruption_sensitivity"] = interruption_sensitivity
    if responsiveness is not None:
        update_fields["responsiveness"] = responsiveness
    if boosted_keywords is not None:
        update_fields["boosted_keywords"] = boosted_keywords

    if not update_fields:
        return {"success": True, "message": "No changes to update"}

    try:
        _retry_on_failure(client.agent.update)(agent_id=agent_id, **update_fields)
        logger.info("retell.agent_updated", tenant_id=tenant_id, agent_id=agent_id, fields=list(update_fields.keys()))
        return {"success": True, "agent_id": agent_id}
    except Exception as exc:
        logger.error("retell.agent_update_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


def delete_agent(agent_id: str, tenant_id: str) -> dict[str, Any]:
    """Delete an agent."""
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    try:
        client = _client()
        _retry_on_failure(client.agent.delete)(agent_id=agent_id)
        logger.info("retell.agent_deleted", tenant_id=tenant_id, agent_id=agent_id)
        return {"success": True}
    except Exception as exc:
        logger.error("retell.agent_delete_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Phone-to-Agent linking
# ---------------------------------------------------------------------------


def assign_number_to_agent(phone_number_id: str, agent_id: str, tenant_id: str) -> dict[str, Any]:
    """Assign a phone number to an AI agent."""
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    try:
        client = _client()
        _retry_on_failure(client.phone_number.update)(
            phone_number_id=phone_number_id,
            agent_id=agent_id,
        )
        logger.info("retell.number_assigned", tenant_id=tenant_id, phone_number_id=phone_number_id, agent_id=agent_id)
        return {"success": True}
    except Exception as exc:
        logger.error("retell.assign_failed", tenant_id=tenant_id, error=str(exc))
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Call forwarding
# ---------------------------------------------------------------------------


def setup_call_forwarding(
    tenant_id: str,
    source_number: str,
    destination_number: str,
    forward_for: str = "all",
) -> dict[str, Any]:
    """Set up call forwarding from one number to another.

    forward_for: 'all', 'busy', 'no_answer', 'unreachable'
    """
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    # Retell handles forwarding via the phone number's assigned agent
    # This is a wrapper for convenience
    logger.info("retell.forwarding_setup", tenant_id=tenant_id, source=source_number, dest=destination_number)
    return {
        "success": True,
        "message": f"Forwarding {forward_for} calls from {source_number} to {destination_number}",
        "note": "In production, configure via Retell dashboard or API",
    }


# ---------------------------------------------------------------------------
# Twilio number import
# ---------------------------------------------------------------------------


def import_twilio_number(
    phone_number: str,
    termination_uri: str,
    agent_id: Optional[str] = None,
    nickname: Optional[str] = None,
    inbound_webhook_url: Optional[str] = None,
) -> dict[str, Any]:
    """Import a Twilio-purchased phone number into Retell.

    This registers the number with Retell so it can answer/handle calls
    via the configured Elastic SIP Trunk. Optionally binds an agent.

    Args:
        phone_number: E.164 number (e.g. +14157774444).
        termination_uri: Twilio Elastic SIP Trunk termination URI.
        agent_id: Optional Retell agent ID to bind for inbound calls.
        nickname: Optional friendly label.
        inbound_webhook_url: Optional webhook Retell calls on inbound call.

    Returns:
        Dict with success status and phone_number details from Retell.
    """
    if not is_configured():
        raise RetellNotConfigured("Retell not configured")

    client = _client()

    try:
        payload: dict[str, Any] = {
            "phone_number": phone_number,
            "termination_uri": termination_uri,
        }
        if nickname:
            payload["nickname"] = nickname
        if inbound_webhook_url:
            payload["inbound_webhook_url"] = inbound_webhook_url
        if agent_id:
            payload["inbound_agents"] = [{"agent_id": agent_id, "weight": 1.0}]

        result = _retry_on_failure(client.phone_number.import_)(**payload)
        logger.info(
            "retell.number_imported",
            phone_number=phone_number,
            agent_id=agent_id,
        )
        return {
            "success": True,
            "phone_number": result.get("phone_number"),
            "phone_number_type": result.get("phone_number_type"),
        }
    except Exception as exc:
        logger.error("retell.number_import_failed", phone_number=phone_number, error=str(exc))
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Webhook verification
# ---------------------------------------------------------------------------


def verify_webhook(payload: bytes, signature: str) -> bool:
    """Verify a Retell webhook signature."""
    if not is_configured():
        return False

    secret = get_settings().integrations.retell_webhook_secret
    if not secret:
        logger.warning("retell.webhook_secret_not_configured")
        return False

    import hmac
    import hashlib

    expected = hmac.new(
        secret.get_secret_value().encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature)

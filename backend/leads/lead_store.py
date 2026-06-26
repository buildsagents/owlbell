from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LEADS_FILE = Path(os.environ.get("OWLBELL_LEADS_FILE", "leads_data.json"))


def _load() -> dict[str, Any]:
    if LEADS_FILE.exists():
        try:
            return json.loads(LEADS_FILE.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"leads": [], "stats": {"total_sent": 0, "total_replied": 0, "total_bounced": 0}}


def _save(data: dict[str, Any]) -> None:
    LEADS_FILE.write_text(json.dumps(data, indent=2, default=str), "utf-8")


def get_all_leads() -> list[dict[str, Any]]:
    data = _load()
    return data["leads"]


def get_lead(email: str) -> Optional[dict[str, Any]]:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            return lead
    return None


def add_lead(lead: dict[str, Any]) -> dict[str, Any]:
    data = _load()
    existing = get_lead(lead["email"])
    if existing:
        return existing
    entry = {
        "name": lead.get("name", ""),
        "email": lead.get("email", ""),
        "phone": lead.get("phone", ""),
        "website": lead.get("website", ""),
        "trade": lead.get("trade", ""),
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "first_contacted": datetime.now(timezone.utc).isoformat(),
        "last_contacted": None,
        "contact_count": 0,
        "follow_up_stage": 0,
        "status": "new",
        "outcomes": [],
    }
    data["leads"].append(entry)
    _save(data)
    return entry


def mark_sent(email: str) -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead["status"] = "sent"
            lead["last_contacted"] = datetime.now(timezone.utc).isoformat()
            lead["contact_count"] = lead.get("contact_count", 0) + 1
            lead["follow_up_stage"] = lead.get("follow_up_stage", 0)
            lead.setdefault("outcomes", []).append({
                "type": "sent",
                "stage": lead["follow_up_stage"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            data["stats"]["total_sent"] = data["stats"].get("total_sent", 0) + 1
            break
    _save(data)


def mark_follow_up_sent(email: str) -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead["follow_up_stage"] = lead.get("follow_up_stage", 0) + 1
            lead["last_contacted"] = datetime.now(timezone.utc).isoformat()
            lead["contact_count"] = lead.get("contact_count", 0) + 1
            lead.setdefault("outcomes", []).append({
                "type": "follow_up",
                "stage": lead["follow_up_stage"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break
    _save(data)


def get_all_sent() -> list[dict[str, Any]]:
    data = _load()
    return [l for l in data["leads"] if l.get("status") == "sent"]


def get_pending_send() -> list[dict[str, Any]]:
    data = _load()
    return [l for l in data["leads"] if l.get("status") == "new"]


def add_reply(email: str, body: str, classification: str) -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead.setdefault("replies", []).append({
                "body": body,
                "classification": classification,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break
    _save(data)


def mark_unsubscribed(email: str) -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead["status"] = "unsubscribed"
            lead.setdefault("outcomes", []).append({
                "type": "unsubscribed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            break
    _save(data)


def mark_replied(email: str, note: str = "") -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead["status"] = "replied"
            lead["last_note"] = note
            lead.setdefault("outcomes", []).append({
                "type": "replied",
                "note": note,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            data["stats"]["total_replied"] = data["stats"].get("total_replied", 0) + 1
            break
    _save(data)


def mark_bounced(email: str) -> None:
    data = _load()
    for lead in data["leads"]:
        if lead["email"] == email:
            lead["status"] = "bounced"
            lead.setdefault("outcomes", []).append({
                "type": "bounced",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            data["stats"]["total_bounced"] = data["stats"].get("total_bounced", 0) + 1
            break
    _save(data)


def get_pending_follow_ups() -> list[dict[str, Any]]:
    data = _load()
    now = datetime.now(timezone.utc)
    pending = []
    for lead in data["leads"]:
        if lead["status"] in ("replied", "bounced", "unsubscribed"):
            continue
        if not lead.get("last_contacted"):
            continue
        last = datetime.fromisoformat(lead["last_contacted"])
        days_since = (now - last).days
        stage = lead.get("follow_up_stage", 0)
        if stage == 0 and days_since >= 3:
            pending.append(lead)
        elif stage == 1 and days_since >= 7:
            pending.append(lead)
    return pending


def get_leads_for_pipeline() -> list[dict[str, Any]]:
    data = _load()
    existing_emails = {l["email"] for l in data["leads"] if l["status"] != "new"}
    return list(existing_emails)


def stats() -> dict[str, Any]:
    data = _load()
    leads = data["leads"]
    return {
        "total": len(leads),
        "sent": sum(1 for l in leads if l["status"] == "sent" or l.get("contact_count", 0) > 0),
        "replied": sum(1 for l in leads if l["status"] == "replied"),
        "bounced": sum(1 for l in leads if l["status"] == "bounced"),
        "pending_follow_ups": len(get_pending_follow_ups()),
        **data.get("stats", {}),
    }

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
    return {
        "leads": [],
        "sent_index": {},
        "stats": {"total_sent": 0, "total_replied": 0, "total_bounced": 0, "total_unsubscribed": 0},
    }


def _save(data: dict[str, Any]) -> None:
    LEADS_FILE.write_text(json.dumps(data, indent=2, default=str), "utf-8")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Lookup helpers ────────────────────────────────────────────


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _domain(email: str) -> str:
    return email.split("@")[-1].lower() if "@" in email else ""


def _normalize_phone(phone: str) -> str:
    return "".join(c for c in phone if c.isdigit())


def get_lead_by_email(email: str) -> Optional[dict[str, Any]]:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            return lead
    return None


def get_lead_by_phone(phone: str) -> Optional[dict[str, Any]]:
    data = _load()
    needle = _normalize_phone(phone)
    if not needle:
        return None
    for lead in data["leads"]:
        if lead.get("phone") and _normalize_phone(lead["phone"]) == needle:
            return lead
    return None


def get_lead_by_domain(domain: str) -> Optional[dict[str, Any]]:
    data = _load()
    d = domain.strip().lower().removeprefix("www.")
    for lead in data["leads"]:
        if lead.get("website"):
            wd = lead["website"].strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.")
            if wd.startswith(d):
                return lead
    return None


# ── Core CRUD ─────────────────────────────────────────────────


def add_lead(lead: dict[str, Any]) -> dict[str, Any]:
    data = _load()

    email = lead.get("email", "").strip()
    phone = lead.get("phone", "").strip()

    # Dedup by email (primary)
    if email:
        existing = get_lead_by_email(email)
        if existing:
            return {**existing, "_new": False}

    # Dedup by phone (secondary)
    if phone:
        existing = get_lead_by_phone(phone)
        if existing:
            return {**existing, "_new": False}

    entry = {
        "name": lead.get("name", ""),
        "email": email,
        "phone": phone,
        "website": lead.get("website", ""),
        "trade": lead.get("trade", ""),
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "rating": lead.get("rating"),
        "review_count": lead.get("review_count", 0),
        "score": lead.get("score", 5),
        "address": lead.get("address", ""),
        "place_id": lead.get("place_id", ""),
        "business_status": lead.get("business_status", ""),
        "source": lead.get("source", "google_places"),
        "created_at": _now(),
        "first_contacted": None,
        "last_contacted": None,
        "contact_count": 0,
        "follow_up_stage": 0,
        "max_follow_ups": lead.get("max_follow_ups", 3),
        "status": "new",
        "sent_emails": [],
        "replies": [],
        "outcomes": [],
        "tags": [],
    }
    data["leads"].append(entry)
    _save(data)
    return {**entry, "_new": True}


def get_all_leads() -> list[dict[str, Any]]:
    return _load()["leads"]


def get_lead_count() -> int:
    return len(_load()["leads"])


# ── Status queries ────────────────────────────────────────────


def get_pending_send(limit: int = 20) -> list[dict[str, Any]]:
    """Leads ready for initial outreach (new, scored > 3, not yet contacted)."""
    data = _load()
    pending = [l for l in data["leads"] if l["status"] == "new" and l.get("score", 0) >= 3]
    pending.sort(key=lambda l: l.get("score", 0), reverse=True)
    return pending[:limit]


def get_pending_follow_ups(limit: int = 30) -> list[dict[str, Any]]:
    """Leads who need follow-up based on their stage timing."""
    data = _load()
    now = datetime.now(timezone.utc)
    pending = []

    FOLLOW_UP_DELAYS = {1: 3, 2: 7, 3: 14}

    for lead in data["leads"]:
        if lead["status"] in ("replied", "bounced", "unsubscribed", "archived"):
            continue
        if not lead.get("last_contacted"):
            continue
        stage = lead.get("follow_up_stage", 0)
        if stage >= lead.get("max_follow_ups", 3):
            continue
        delay = FOLLOW_UP_DELAYS.get(stage + 1, 7)
        last = datetime.fromisoformat(lead["last_contacted"])
        days_since = (now - last).days
        if days_since >= delay:
            pending.append(lead)

    pending.sort(key=lambda l: l.get("follow_up_stage", 0))
    return pending[:limit]


def get_leads_needing_scoring(limit: int = 50) -> list[dict[str, Any]]:
    data = _load()
    unscored = [l for l in data["leads"] if l.get("score", 0) == 0 and l.get("status") == "new"]
    return unscored[:limit]


# ── Mutations ─────────────────────────────────────────────────


def mark_sent(email: str, subject: str = "", body_preview: str = "") -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["status"] = "sent"
            lead["first_contacted"] = lead["first_contacted"] or _now()
            lead["last_contacted"] = _now()
            lead["contact_count"] = lead.get("contact_count", 0) + 1
            entry = {
                "type": "initial",
                "stage": lead.get("follow_up_stage", 0) + 1,
                "subject": subject,
                "preview": body_preview[:120] if body_preview else "",
                "timestamp": _now(),
            }
            lead.setdefault("sent_emails", []).append(entry)
            lead.setdefault("outcomes", []).append({"type": "sent", **entry})
            data["stats"]["total_sent"] = data["stats"].get("total_sent", 0) + 1
            data["sent_index"][needle] = True
            break
    _save(data)


def mark_follow_up_sent(email: str, subject: str = "", body_preview: str = "") -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["follow_up_stage"] = lead.get("follow_up_stage", 0) + 1
            lead["last_contacted"] = _now()
            lead["contact_count"] = lead.get("contact_count", 0) + 1
            entry = {
                "type": "follow_up",
                "stage": lead["follow_up_stage"],
                "subject": subject,
                "preview": body_preview[:120] if body_preview else "",
                "timestamp": _now(),
            }
            lead.setdefault("sent_emails", []).append(entry)
            lead.setdefault("outcomes", []).append({"type": "follow_up", **entry})
            break
    _save(data)


def add_reply(email: str, body: str, classification: str) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead.setdefault("replies", []).append({
                "body": body,
                "classification": classification,
                "timestamp": _now(),
            })
            break
    _save(data)


def mark_replied(email: str, note: str = "") -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["status"] = "replied"
            lead["last_note"] = note
            lead.setdefault("outcomes", []).append({
                "type": "replied",
                "note": note,
                "timestamp": _now(),
            })
            data["stats"]["total_replied"] = data["stats"].get("total_replied", 0) + 1
            break
    _save(data)


def mark_unsubscribed(email: str) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["status"] = "unsubscribed"
            lead.setdefault("outcomes", []).append({"type": "unsubscribed", "timestamp": _now()})
            data["stats"]["total_unsubscribed"] = data["stats"].get("total_unsubscribed", 0) + 1
            break
    _save(data)


def mark_bounced(email: str) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["status"] = "bounced"
            lead.setdefault("outcomes", []).append({"type": "bounced", "timestamp": _now()})
            data["stats"]["total_bounced"] = data["stats"].get("total_bounced", 0) + 1
            break
    _save(data)


def mark_archived(email: str) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["status"] = "archived"
            lead.setdefault("outcomes", []).append({"type": "archived", "timestamp": _now()})
            break
    _save(data)


def update_score(email: str, score: int) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            lead["score"] = max(1, min(10, score))
            break
    _save(data)


def update_lead(email: str, **kwargs) -> None:
    data = _load()
    needle = _normalize_email(email)
    for lead in data["leads"]:
        if lead.get("email") and _normalize_email(lead["email"]) == needle:
            for k, v in kwargs.items():
                if v is not None:
                    lead[k] = v
            break
    _save(data)


# ── Bulk helpers ──────────────────────────────────────────────


# ── Discovery queue ───────────────────────────────────────────


def get_discovery_queue() -> list[dict[str, Any]]:
    return _load().get("_discovery_queue", [])


def set_discovery_queue(queue: list[dict[str, Any]]) -> None:
    data = _load()
    data["_discovery_queue"] = queue
    _save(data)


# ── Bulk helpers ──────────────────────────────────────────────


def already_sent_to(email: str) -> bool:
    data = _load()
    return _normalize_email(email) in data.get("sent_index", {})


def get_all_sent() -> list[dict[str, Any]]:
    data = _load()
    return [l for l in data["leads"] if l.get("status") in ("sent", "replied", "followed_up")]


def get_leads_for_pipeline() -> list[str]:
    data = _load()
    return list(data.get("sent_index", {}).keys())


def stats() -> dict[str, Any]:
    data = _load()
    leads = data["leads"]
    total = len(leads)
    sent = sum(1 for l in leads if l.get("status") == "sent")
    replied = sum(1 for l in leads if l.get("status") == "replied")
    bounced = sum(1 for l in leads if l.get("status") == "bounced")
    unsubscribed = sum(1 for l in leads if l.get("status") == "unsubscribed")
    archived = sum(1 for l in leads if l.get("status") == "archived")
    pending = sum(1 for l in leads if l.get("status") == "new")
    has_email = sum(1 for l in leads if l.get("email"))
    has_phone = sum(1 for l in leads if l.get("phone"))
    avg_score = sum(l.get("score", 0) for l in leads) / max(total, 1)

    follow_up_counts = {}
    for l in leads:
        stage = l.get("follow_up_stage", 0)
        follow_up_counts[str(stage)] = follow_up_counts.get(str(stage), 0) + 1

    return {
        "total": total,
        "sent": sent,
        "replied": replied,
        "bounced": bounced,
        "unsubscribed": unsubscribed,
        "archived": archived,
        "pending": pending,
        "with_email": has_email,
        "with_phone": has_phone,
        "avg_score": round(avg_score, 1),
        "follow_up_stages": follow_up_counts,
        "total_sent": data["stats"].get("total_sent", 0),
        "total_replied": data["stats"].get("total_replied", 0),
        "total_bounced": data["stats"].get("total_bounced", 0),
        "total_unsubscribed": data["stats"].get("total_unsubscribed", 0),
    }

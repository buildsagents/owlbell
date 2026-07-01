"""File-backed training feedback store (durable across restarts).

Used by operations/admin AdminService until a dedicated DB table exists.
Writes are atomic via temp-file rename.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_STORE_PATH = Path(os.environ.get("OWLBELL_FEEDBACK_FILE", "training_feedback.json"))


def _load() -> list[dict[str, Any]]:
    if not _STORE_PATH.exists():
        return []
    try:
        data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(entries: list[dict[str, Any]]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def append_feedback(
    *,
    call_id: str,
    feedback: str,
    rating: int,
    corrected_transcript: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    entry = {
        "id": str(uuid.uuid4()),
        "call_id": call_id,
        "feedback": feedback,
        "rating": rating,
        "corrected_transcript": corrected_transcript,
        "submitted_by": user_id,
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_review",
    }
    entries = _load()
    entries.append(entry)
    _save(entries)
    return entry


def list_feedback(
    *,
    call_id: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    entries = _load()
    if call_id:
        entries = [e for e in entries if e.get("call_id") == call_id]
    return entries[-limit:]
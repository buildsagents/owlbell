"""Script version history stored in tenant config (server-side, RAG-adjacent)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

MAX_VERSIONS = 12


def _versions_bucket(config_json: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    raw = (config_json or {}).get("script_versions") or {}
    return dict(raw) if isinstance(raw, dict) else {}


def list_script_versions(config_json: dict[str, Any] | None, script_key: str) -> list[dict[str, Any]]:
    bucket = _versions_bucket(config_json)
    rows = bucket.get(script_key) or []
    return list(rows) if isinstance(rows, list) else []


def append_script_version(
    config_json: dict[str, Any] | None,
    *,
    script_key: str,
    content: str,
    label: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (updated_config_json, new_version_row)."""
    base = dict(config_json or {})
    bucket = _versions_bucket(base)
    existing = list_script_versions(base, script_key)
    version = {
        "id": str(uuid4()),
        "label": label or f"v{len(existing) + 1}",
        "content": content,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    bucket[script_key] = [version, *existing][:MAX_VERSIONS]
    base["script_versions"] = bucket
    return base, version
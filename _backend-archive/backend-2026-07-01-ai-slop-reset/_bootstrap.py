"""Package bootstrap — re-exports from ``import_roots`` (``backend._bootstrap``)."""

from __future__ import annotations

from backend.import_roots import (  # noqa: F401
    BACKEND_DIR,
    PROJECT_ROOT,
    ensure_import_paths,
    pythonpath_env_value,
    register_namespace_alias,
)

__all__ = [
    "BACKEND_DIR",
    "PROJECT_ROOT",
    "ensure_import_paths",
    "pythonpath_env_value",
    "register_namespace_alias",
]
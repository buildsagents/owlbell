"""Test utilities — import root paths (provided by editable install)."""

from __future__ import annotations

from backend.import_roots import BACKEND_DIR, PROJECT_ROOT, ensure_import_paths

__all__ = ["BACKEND_DIR", "PROJECT_ROOT", "ensure_test_import_paths"]


def ensure_test_import_paths() -> tuple[str, str]:
    """Return configured import roots (no-op when ``pip install -e .`` is active)."""
    return ensure_import_paths()
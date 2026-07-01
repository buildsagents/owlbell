"""api/main.py — Deprecated entrypoint shim.

Use ``backend.app_factory.create_app()`` or ``backend.main:app`` instead.
This module exists for backward compatibility with older deploy scripts.
"""

from __future__ import annotations

from backend.app_factory import API_PREFIX, APP_VERSION, EXEMPT_PATHS, create_app

__all__ = ["app", "create_app", "API_PREFIX", "APP_VERSION", "EXEMPT_PATHS"]

app = create_app()
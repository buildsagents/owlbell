"""Legacy script bootstrap — prefer ``pip install -e .`` from ``project/``.

Delegates to ``import_roots``. Only needed for standalone scripts run before
``import backend`` (e.g. ``path_setup`` imported from ``verify_goal`` preamble).
"""

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
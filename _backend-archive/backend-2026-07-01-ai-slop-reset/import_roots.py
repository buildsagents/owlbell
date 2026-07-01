"""Dual-root sys.path bootstrap for the Owlbell split layout.

Install once from the project root (canonical ``pyproject.toml`` lives there)::

    cd project/
    pip install -e ".[dev]" --no-deps

That registers ``project/`` on ``sys.path`` via an editable ``.pth`` file.
``import backend`` then adds ``project/backend/`` for top-level ``api``,
``workers``, etc. No manual ``PYTHONPATH`` is required in tests or scripts.

``_owlbell_paths.pth`` (installed with the package) and ``backend._install_paths``
wire both roots on interpreter startup so deploy matches local dev.

``ensure_import_paths()`` remains as a dev/script fallback when the package
is not installed.
"""

from __future__ import annotations

import os
import sys
import types

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)

__all__ = [
    "BACKEND_DIR",
    "PROJECT_ROOT",
    "ensure_import_paths",
    "import_paths_configured",
    "pythonpath_env_value",
    "register_namespace_alias",
]


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def import_paths_configured() -> bool:
    """Return True when both import roots are already on ``sys.path``."""
    want = {_norm(PROJECT_ROOT), _norm(BACKEND_DIR)}
    have = {_norm(p) for p in sys.path}
    return want.issubset(have)


def ensure_import_paths() -> tuple[str, str]:
    """Prepend project root and backend dir to ``sys.path`` (idempotent)."""
    if import_paths_configured():
        return PROJECT_ROOT, BACKEND_DIR
    for path in (PROJECT_ROOT, BACKEND_DIR):
        norm = _norm(path)
        if not any(_norm(p) == norm for p in sys.path):
            sys.path.insert(0, path)
    return PROJECT_ROOT, BACKEND_DIR


def pythonpath_env_value() -> str:
    """Legacy: value for ``PYTHONPATH`` when spawning child processes."""
    return os.pathsep.join((PROJECT_ROOT, BACKEND_DIR))


def register_namespace_alias(module: types.ModuleType) -> None:
    """Mirror ``pkg`` ↔ ``backend.pkg`` so both import styles share one module."""
    name = module.__name__
    if name.startswith("backend."):
        short = name[len("backend.") :]
        if short:
            sys.modules.setdefault(short, module)
    elif "." not in name:
        sys.modules.setdefault(f"backend.{name}", module)
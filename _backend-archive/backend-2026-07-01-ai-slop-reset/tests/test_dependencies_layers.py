"""Guard: api.dependencies and backend.dependencies stay in separate layers."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
API_DEPS = BACKEND_ROOT / "api" / "dependencies.py"
SVC_DEPS = BACKEND_ROOT / "dependencies.py"


def _import_modules(module_names: list[str]) -> None:
    for name in module_names:
        importlib.import_module(name)


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
    return found


def test_api_dependencies_never_imports_backend_dependencies() -> None:
    imports = _top_level_imports(API_DEPS)
    assert "backend.dependencies" not in imports
    assert not any(m == "backend.dependencies" or m.startswith("backend.dependencies.") for m in imports)


def test_backend_dependencies_never_imports_api_dependencies() -> None:
    imports = _top_level_imports(SVC_DEPS)
    assert "api.dependencies" not in imports
    assert not any(m == "api.dependencies" or m.startswith("api.dependencies.") for m in imports)


def test_backend_dependencies_uses_di_container_not_globals() -> None:
    imports = _top_level_imports(SVC_DEPS)
    assert "backend.di" in imports


def test_api_dependencies_imports_session_from_db_not_services() -> None:
    imports = _top_level_imports(API_DEPS)
    assert "backend.db.session" in imports
    assert "backend.dependencies" not in imports


def test_both_dependency_modules_load_without_cycle() -> None:
    import sys

    for key in list(sys.modules):
        if key in ("api.dependencies", "backend.dependencies"):
            del sys.modules[key]
    _import_modules(["backend.dependencies", "api.dependencies"])
    _import_modules(["api.dependencies", "backend.dependencies"])
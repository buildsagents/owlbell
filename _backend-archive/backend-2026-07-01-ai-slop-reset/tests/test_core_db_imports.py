"""Guard: core DB layer and downstream modules import without PYTHONPATH hacks."""

from __future__ import annotations

import os
import subprocess
import sys

from backend.import_roots import BACKEND_DIR, PROJECT_ROOT


def _run_probe(code: str, *, cwd: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )


_CORE_PROBE = """
from backend.db.session import init_engine, require_session_maker
from backend.db import models
from ai.tools.registry import ToolRegistry, get_tool_registry
from api.middleware import TenantMiddleware, TenantContext
from api.tenant_lookup import lookup_tenant_by_id, lookup_tenant_by_slug, tenant_id_from_jwt_header
assert callable(require_session_maker)
assert ToolRegistry is not None
assert callable(get_tool_registry)
assert TenantMiddleware is not None
assert callable(lookup_tenant_by_id)
print("CORE_IMPORTS_OK")
"""


def test_core_db_imports_from_backend_cwd() -> None:
    result = _run_probe(_CORE_PROBE, cwd=BACKEND_DIR)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "CORE_IMPORTS_OK" in result.stdout


def test_core_db_imports_from_project_cwd() -> None:
    result = _run_probe(_CORE_PROBE, cwd=PROJECT_ROOT)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "CORE_IMPORTS_OK" in result.stdout


def test_registry_db_session_resolution() -> None:
    """ToolRegistry must resolve DB via backend.db.session, not api.dependencies."""
    from ai.tools import registry as reg_mod

    source = open(reg_mod.__file__, encoding="utf-8").read()
    assert "from backend.db.session import require_session_maker" in source
    assert "api.dependencies" not in source


def _module_top_level_lines(path: str) -> list[str]:
    """Lines before the first top-level def/class (module import block)."""
    lines: list[str] = []
    for line in open(path, encoding="utf-8"):
        stripped = line.strip()
        if stripped.startswith("def ") or stripped.startswith("class ") or stripped.startswith("async def "):
            if not line.startswith((" ", "\t")):
                break
        lines.append(line)
    return lines


def test_core_modules_have_no_top_level_api_imports() -> None:
    """registry, middleware, tenant_lookup must not use bare top-level `from api.*`."""
    from ai.tools import registry as reg_mod
    import api.middleware as middleware_mod
    import api.tenant_lookup as tenant_mod

    for mod in (reg_mod, middleware_mod, tenant_mod):
        top = "".join(_module_top_level_lines(mod.__file__))
        assert "from api." not in top, mod.__name__
        assert "import api." not in top, mod.__name__
"""Guard: imports behave the same without PYTHONPATH (Windows dev == Linux deploy)."""

from __future__ import annotations

import os
import subprocess
import sys

from backend.import_roots import BACKEND_DIR, PROJECT_ROOT


def _run_import_probe(code: str, *, cwd: str) -> subprocess.CompletedProcess[str]:
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


def test_top_level_imports_without_pythonpath_from_backend_cwd() -> None:
    """Celery/uvicorn-style cwd=backend must resolve workers + api."""
    code = """
from backend.import_roots import BACKEND_DIR, PROJECT_ROOT, import_paths_configured
assert import_paths_configured(), (BACKEND_DIR, PROJECT_ROOT)
import api.routes.auth  # noqa: F401
import workers.celery_app  # noqa: F401
from workers.celery_app import celery_app
assert celery_app is not None
print("OK")
"""
    result = _run_import_probe(code, cwd=BACKEND_DIR)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout


def test_top_level_imports_without_pythonpath_from_project_root() -> None:
    """Docker WORKDIR=/app layout (project root) must resolve the same modules."""
    code = """
from backend.import_roots import import_paths_configured
assert import_paths_configured()
import api.routes.onboarding  # noqa: F401
from backend.app_factory import create_app
app = create_app(env="testing")
assert hasattr(app.state, "container")
print("OK")
"""
    result = _run_import_probe(code, cwd=PROJECT_ROOT)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout


def test_celery_entrypoint_imports_without_path_setup() -> None:
    """Workers must not depend on legacy bare path_setup import."""
    code = """
from workers.celery_app import celery_app
import workers.onboarding_tasks  # noqa: F401 — register tasks
import workers.analytics_tasks  # noqa: F401
assert celery_app.main == "owlbell"
assert "workers.provision_retell" in celery_app.tasks
print("OK")
"""
    result = _run_import_probe(code, cwd=BACKEND_DIR)
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout


def test_package_modules_use_backend_import_roots_not_bare_import() -> None:
    """Top-level packages must import backend.import_roots (deploy-safe)."""
    import api
    import domain
    import operations
    import workers

    for module in (api, domain, operations, workers):
        source_path = getattr(module, "__file__", "") or ""
        assert source_path
        text = open(source_path, encoding="utf-8").read()
        assert "from backend.import_roots import" in text
        assert "from import_roots import" not in text
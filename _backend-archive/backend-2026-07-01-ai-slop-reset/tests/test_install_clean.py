"""Guard: installed package resolves imports without PYTHONPATH manipulation."""

from __future__ import annotations

import os
import subprocess
import sys

from backend.import_roots import BACKEND_DIR, PROJECT_ROOT, import_paths_configured


def test_editable_install_configures_import_paths() -> None:
    """pip install -e . must put both roots on sys.path via site-packages .pth."""
    assert import_paths_configured(), (
        "Import roots missing — run: pip install -e . from project/backend/"
    )


def test_imports_without_pythonpath_env() -> None:
    """Subprocess imports must work with PYTHONPATH unset (installed package only)."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    code = """
import backend  # editable install + bootstrap adds backend/ to sys.path
from backend.domain import get_orchestrator
from backend.domain.analytics import rollup_all_tenants_for_day
from backend.db.session import get_session_maker
from workers.celery_app import celery_app
assert callable(get_orchestrator)
assert callable(rollup_all_tenants_for_day)
assert callable(get_session_maker)
assert celery_app is not None
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout


def test_subprocess_without_pythonpath_from_project_root() -> None:
    """Imports work from project/ cwd with no PYTHONPATH (typical CI invocation)."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    code = """
import backend
from backend.domain.onboarding.orchestrator import get_orchestrator
print("OK")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    assert "OK" in result.stdout
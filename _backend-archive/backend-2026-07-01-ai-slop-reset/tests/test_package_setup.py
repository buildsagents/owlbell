"""Guard: package __init__.py files export public API and bootstrap imports."""

from __future__ import annotations

import importlib
import subprocess
import sys

import pytest

from tests._path_bootstrap import BACKEND_DIR, PROJECT_ROOT, ensure_test_import_paths

# Packages that must define __all__ and resolve chained imports.
PACKAGE_SPECS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("backend.domain", ("get_orchestrator", "OnboardingOrchestrator")),
    ("backend.domain.onboarding", ("get_orchestrator", "OnboardingOrchestrator")),
    ("backend.domain.analytics", ("rollup_all_tenants_for_day", "compute_period_metrics")),
    ("backend.operations", ("TenantManager", "UsageTracker", "automation")),
    ("backend.operations.onboarding", ("automation", "email_sequence")),
    ("backend.operations.tenant", ("TenantManager",)),
    ("backend.operations.billing", ("UsageTracker", "PlanManager")),
    ("backend.operations.features", ("FeatureFlags", "FeatureFlagService")),
    ("backend.import_roots", ("ensure_import_paths", "register_namespace_alias")),
    ("backend._bootstrap", ("ensure_import_paths",)),
)


@pytest.mark.parametrize("module_name,exports", PACKAGE_SPECS)
def test_package_init_exports(module_name: str, exports: tuple[str, ...]) -> None:
    ensure_test_import_paths()
    module = importlib.import_module(module_name)
    assert hasattr(module, "__all__"), f"{module_name} missing __all__"
    for symbol in exports:
        assert symbol in module.__all__, f"{module_name}.__all__ missing {symbol!r}"
        assert hasattr(module, symbol), f"{module_name} missing export {symbol!r}"


def test_namespace_aliases_domain_and_operations() -> None:
    ensure_test_import_paths()
    import backend.domain
    import domain

    assert domain is backend.domain

    import backend.operations
    import operations

    assert operations is backend.operations


def test_domain_get_orchestrator_via_package_root() -> None:
    ensure_test_import_paths()
    from backend.domain import get_orchestrator

    assert callable(get_orchestrator)


def test_chained_import_subprocess_without_pythonpath() -> None:
    import os

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    code = """
import backend
from backend.domain import get_orchestrator
from backend.domain.analytics import rollup_all_tenants_for_day
from backend.operations.onboarding import automation
assert callable(get_orchestrator)
assert callable(rollup_all_tenants_for_day)
assert automation is not None
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
"""Operations layer — tenant, billing, onboarding, admin, audit, features."""

from __future__ import annotations

import sys

from backend.import_roots import ensure_import_paths, register_namespace_alias

ensure_import_paths()

from backend.operations.billing import PlanManager, UsageTracker
from backend.operations.onboarding import automation, email_sequence
from backend.operations.tenant import TenantManager

__all__ = [
    "TenantManager",
    "UsageTracker",
    "PlanManager",
    "automation",
    "email_sequence",
    "tenant",
    "billing",
    "onboarding",
    "admin",
    "audit",
    "features",
    "prompts",
]

register_namespace_alias(sys.modules[__name__])


def __getattr__(name: str):
    _subpackages = {
        "tenant": "backend.operations.tenant",
        "billing": "backend.operations.billing",
        "onboarding": "backend.operations.onboarding",
        "admin": "backend.operations.admin",
        "audit": "backend.operations.audit",
        "features": "backend.operations.features",
        "prompts": "backend.operations.prompts",
    }
    if name in _subpackages:
        import importlib

        return importlib.import_module(_subpackages[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
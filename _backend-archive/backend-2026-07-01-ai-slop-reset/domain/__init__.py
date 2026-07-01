"""Domain services — business logic isolated from HTTP routes."""

from __future__ import annotations

import sys

from backend.import_roots import ensure_import_paths, register_namespace_alias

ensure_import_paths()

from backend.domain.onboarding import OnboardingOrchestrator, get_orchestrator

__all__ = [
    "OnboardingOrchestrator",
    "get_orchestrator",
    "onboarding",
    "analytics",
]

register_namespace_alias(sys.modules[__name__])


def __getattr__(name: str):
    if name == "onboarding":
        import backend.domain.onboarding as onboarding

        return onboarding
    if name == "analytics":
        import backend.domain.analytics as analytics

        return analytics
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
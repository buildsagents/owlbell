"""FastAPI application layer — routes, middleware, dependencies."""

from __future__ import annotations

import sys

from backend.import_roots import ensure_import_paths, register_namespace_alias

ensure_import_paths()

__all__ = ["dependencies", "middleware", "routes", "main"]

register_namespace_alias(sys.modules[__name__])


def __getattr__(name: str):
    if name == "dependencies":
        import api.dependencies as dependencies

        return dependencies
    if name == "middleware":
        import api.middleware as middleware

        return middleware
    if name == "routes":
        import api.routes as routes

        return routes
    if name == "main":
        import api.main as main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
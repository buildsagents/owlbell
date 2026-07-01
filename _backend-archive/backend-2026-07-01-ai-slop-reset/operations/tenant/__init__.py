"""operations/tenant - Tenant lifecycle management."""

from backend.operations.tenant.manager import TenantManager

__all__ = [
    "TenantManager",
    "TenantMiddleware",
    "TenantResolutionMiddleware",
    "TenantValidationMiddleware",
]


def __getattr__(name: str):
    """Lazy-load middleware to avoid circular imports with manager."""
    if name == "TenantMiddleware":
        from backend.operations.tenant.middleware import TenantResolutionMiddleware

        return TenantResolutionMiddleware
    if name == "TenantResolutionMiddleware":
        from backend.operations.tenant.middleware import TenantResolutionMiddleware

        return TenantResolutionMiddleware
    if name == "TenantValidationMiddleware":
        from backend.operations.tenant.middleware import TenantValidationMiddleware

        return TenantValidationMiddleware
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
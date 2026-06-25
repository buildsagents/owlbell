"""Stripe billing integration for Owlbell.

Exposes a thin service layer over the Stripe API for subscription checkout,
the customer billing portal, and webhook handling. Import-safe: the ``stripe``
package is imported lazily so the app runs even when billing is not configured.
"""

from . import service  # noqa: F401

__all__ = ["service"]

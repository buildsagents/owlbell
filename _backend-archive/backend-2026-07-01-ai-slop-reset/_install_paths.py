"""Install dual import roots on interpreter startup (editable, wheel, Docker).

Registered via ``_owlbell_paths.pth`` so ``api``, ``workers``, and ``operations``
resolve the same way on Windows dev, Linux CI, and production containers —
without manual ``PYTHONPATH`` or importing ``backend`` first.
"""

from __future__ import annotations


def install() -> None:
    from backend.import_roots import ensure_import_paths

    ensure_import_paths()


__all__ = ["install"]
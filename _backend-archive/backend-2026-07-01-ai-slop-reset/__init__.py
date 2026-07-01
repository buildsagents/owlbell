"""
Owlbell — Backend Package.

AI-powered 24/7 phone answering service for businesses.
Zero-budget, open-source stack: FreeSWITCH + Whisper + Ollama + Piper.
"""

from __future__ import annotations

import sys

from backend._bootstrap import ensure_import_paths, register_namespace_alias
from backend._install_paths import install as _install_import_paths

_install_import_paths()
ensure_import_paths()
register_namespace_alias(sys.modules[__name__])

__version__ = "1.0.0"
__app_name__ = "Owlbell"

__all__ = ["__version__", "__app_name__"]
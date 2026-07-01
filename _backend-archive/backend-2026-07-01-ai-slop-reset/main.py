"""
Owlbell — Application entry point.

Production: ``uvicorn backend.app_factory:create_prod_app --factory``
Development: ``uvicorn backend.main:app --reload``

All HTTP wiring lives in ``backend.app_factory`` (single factory).
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def setup_logging() -> None:
    env = os.getenv("APP_ENV", "development").lower()
    log_level = os.getenv("LOG_LEVEL", "DEBUG" if env in ("development", "dev", "testing") else "INFO")
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )
    shared = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
    ]
    processors = shared + (
        [structlog.dev.ConsoleRenderer(colors=True)]
        if env in ("development", "dev", "testing")
        else [structlog.processors.JSONRenderer()]
    )
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


setup_logging()

from backend.app_factory import create_app  # noqa: E402
from backend.config import get_settings  # noqa: E402

_settings = get_settings()
app = create_app(settings=_settings)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=_settings.api_host,
        port=_settings.api_port,
        reload=_settings.is_development,
        log_level="debug" if _settings.debug else "info",
    )
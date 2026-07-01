"""Run async coroutines from synchronous Celery task bodies."""

from __future__ import annotations

import asyncio
import sys

_loop: asyncio.AbstractEventLoop | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def run_async(coro):
    """Execute one coroutine on a persistent worker event loop."""
    return _ensure_loop().run_until_complete(coro)
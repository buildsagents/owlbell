"""
manager.py — Telephony manager that ties ESL + CallHandler to the app lifecycle.

Started by main.py's SubsystemManager._start_freeswitch().
Owns the ESLConnection and CallHandler instances.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import structlog

from telephony.core.esl_connection import ESLConnection
from telephony.core.call_handler import CallHandler

logger = structlog.get_logger(__name__)


class TelephonyManager:
    """Manages the FreeSWITCH telephony subsystem.

    Lifecycle:
        manager = TelephonyManager(settings)
        await manager.start(session_manager, event_bus, ai_pipeline)
        # ... runs for app lifetime ...
        await manager.stop()
    """

    def __init__(self, settings: Any):
        self.settings = settings
        self.esl: Optional[ESLConnection] = None
        self.call_handler: Optional[CallHandler] = None
        self._started = False

    async def start(
        self,
        session_manager: Any,
        event_bus: Any,
        ai_pipeline: Any,
    ) -> None:
        """Initialize and connect the telephony subsystem."""
        fs_settings = self.settings.freeswitch

        # Create ESL connection
        self.esl = ESLConnection(
            host=fs_settings.host,
            port=fs_settings.esl_port,
            password=fs_settings.esl_password.get_secret_value()
                if hasattr(fs_settings.esl_password, 'get_secret_value')
                else str(fs_settings.esl_password),
            reconnect_interval=1.0,
            max_reconnect_interval=30.0,
        )

        # Create call handler
        self.call_handler = CallHandler(
            esl=self.esl,
            session_manager=session_manager,
            event_bus=event_bus,
            ai_pipeline=ai_pipeline,
            settings=self.settings,
        )

        # Register event handlers
        self.call_handler.register()

        # Connect to FreeSWITCH (non-blocking — runs in background)
        import asyncio
        asyncio.create_task(self._connect_loop())

        self._started = True
        logger.info("telephony.manager.started", host=fs_settings.host, port=fs_settings.esl_port)

    async def _connect_loop(self) -> None:
        """Connect to FreeSWITCH, retrying until success."""
        try:
            await self.esl.connect()
        except Exception as exc:
            logger.error("telephony.manager.connect_failed", error=str(exc))
            # ESLConnection has its own retry logic, but if it exits
            # we should log and let the app continue (degraded mode)
            logger.warning("telephony.manager.degraded_mode", reason="FreeSWITCH not connected")

    async def stop(self) -> None:
        """Shut down the telephony subsystem."""
        if self.esl:
            await self.esl.disconnect()
        self._started = False
        logger.info("telephony.manager.stopped")

    @property
    def healthy(self) -> bool:
        """Whether the telephony subsystem is connected and operational."""
        return self._started and self.esl is not None and self.esl.connected

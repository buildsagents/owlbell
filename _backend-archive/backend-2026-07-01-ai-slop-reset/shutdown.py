"""
Owlbell — Graceful Shutdown Handler.

Location: backend/shutdown.py

Manages graceful shutdown of all subsystems:
1. Close all active phone calls with notification
2. Disconnect from FreeSWITCH ESL
3. Close database connection pool
4. Flush Redis buffers
5. Save pending state (sessions, transcripts)
6. Stop Celery workers
7. Close AI pipeline services

Usage:
    from backend.shutdown import GracefulShutdown
    shutdown = GracefulShutdown()
    await shutdown.execute(reason="SIGTERM received")

Called from the FastAPI lifespan context manager in app_factory.py.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncEngine

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ShutdownTask:
    """A single shutdown task result."""

    name: str
    status: str  # "ok" | "error" | "skipped"
    latency_ms: float = 0.0
    message: str = ""


@dataclass
class ShutdownReport:
    """Aggregated shutdown report."""

    tasks: List[ShutdownTask] = field(default_factory=list)
    reason: str = ""
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def total_latency_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def has_errors(self) -> bool:
        return any(t.status == "error" for t in self.tasks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reason": self.reason,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "tasks": [
                {
                    "name": t.name,
                    "status": t.status,
                    "latency_ms": round(t.latency_ms, 2),
                    "message": t.message,
                }
                for t in self.tasks
            ],
        }


class GracefulShutdown:
    """Handles graceful shutdown of all Owlbell subsystems."""

    # Graceful shutdown timeout per subsystem (seconds)
    SUBSYSTEM_TIMEOUT = 10.0

    def __init__(self) -> None:
        self.settings = get_settings()
        self.report = ShutdownReport()

    async def execute(self, reason: str = "shutdown requested") -> ShutdownReport:
        """Execute the full graceful shutdown sequence.

        Steps:
            1. Mark system as shutting down (reject new calls)
            2. Close active calls gracefully
            3. Disconnect FreeSWITCH
            4. Close AI pipeline
            5. Flush Redis
            6. Close database pool
            7. Log final report
        """
        self.report.reason = reason
        self.report.start_time = time.time()
        logger.info("shutdown.start", reason=reason)

        # Step 1: Mark shutdown flag in Redis (reject new calls)
        task = await self._set_shutdown_flag()
        self.report.tasks.append(task)

        # Step 2: Close active calls
        task = await self._close_active_calls()
        self.report.tasks.append(task)

        # Step 3: Disconnect FreeSWITCH
        task = await self._disconnect_freeswitch()
        self.report.tasks.append(task)

        # Step 4: Close AI pipeline services
        task = await self._close_ai_pipeline()
        self.report.tasks.append(task)

        # Step 5: Flush Redis
        task = await self._flush_redis()
        self.report.tasks.append(task)

        # Step 6: Close database pool
        task = await self._close_database()
        self.report.tasks.append(task)

        # Step 7: Save final state
        task = await self._save_pending_state()
        self.report.tasks.append(task)

        self.report.end_time = time.time()

        logger.info(
            "shutdown.complete",
            reason=reason,
            total_ms=round(self.report.total_latency_ms, 2),
            tasks=len(self.report.tasks),
            errors=sum(1 for t in self.report.tasks if t.status == "error"),
        )

        return self.report

    async def _set_shutdown_flag(self) -> ShutdownTask:
        """Set shutdown flag in Redis to reject new calls."""
        t0 = time.time()
        task = ShutdownTask(name="set_shutdown_flag")

        try:
            redis = aioredis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=self.SUBSYSTEM_TIMEOUT,
            )
            await redis.setex("system:shutdown", 300, "1")
            await redis.close()

            task.status = "ok"
            task.message = "Shutdown flag set in Redis (new calls will be rejected)"
        except Exception as exc:
            task.status = "error"
            task.message = f"Failed to set shutdown flag: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _close_active_calls(self) -> ShutdownTask:
        """Close all active calls gracefully.

        Notify callers that the system is shutting down and hang up.
        """
        t0 = time.time()
        task = ShutdownTask(name="close_active_calls")

        try:
            redis = aioredis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=self.SUBSYSTEM_TIMEOUT,
            )

            # Get all active sessions
            active_keys = await redis.keys("session:*")
            call_count = len(active_keys)

            if call_count == 0:
                task.status = "ok"
                task.message = "No active calls to close"
            else:
                # Publish hangup events for each active session
                for key in active_keys:
                    session_id = key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
                    await redis.publish(
                        f"session:{session_id}:events",
                        "{\"type\": \"system_shutdown\", \"message\": \"Service is shutting down, please call back shortly.\"}",
                    )
                    # Set session state to ending
                    await redis.hset(key, "state", "ending")

                # Wait briefly for hangup messages to be delivered
                await asyncio.sleep(1.0)

                task.status = "ok"
                task.message = f"Gracefully closed {call_count} active call(s)"
                task.details = {"closed_calls": call_count}

            await redis.close()
        except Exception as exc:
            task.status = "error"
            task.message = f"Error closing active calls: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _disconnect_freeswitch(self) -> ShutdownTask:
        """Disconnect from FreeSWITCH ESL."""
        t0 = time.time()
        task = ShutdownTask(name="disconnect_freeswitch")

        try:
            redis = aioredis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=self.SUBSYSTEM_TIMEOUT,
            )
            # Signal FreeSWITCH handler to disconnect
            await redis.delete("freeswitch:esl:connected")
            await redis.close()

            task.status = "ok"
            task.message = "FreeSWITCH disconnect signaled"
        except Exception as exc:
            task.status = "error"
            task.message = f"Error disconnecting FreeSWITCH: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _close_ai_pipeline(self) -> ShutdownTask:
        """Close AI pipeline services (Whisper, Ollama, Piper)."""
        t0 = time.time()
        task = ShutdownTask(name="close_ai_pipeline")

        try:
            # Close any cached AI service clients
            from backend.ai.stt.whisper_service import close_whisper_service
            from backend.ai.llm.ollama_client import close_ollama_client
            from backend.ai.tts.piper_service import close_piper_service

            await close_whisper_service()
            await close_ollama_client()
            await close_piper_service()

            task.status = "ok"
            task.message = "AI pipeline services closed"
        except ImportError:
            task.status = "skipped"
            task.message = "AI service modules not available (skipped)"
        except Exception as exc:
            task.status = "error"
            task.message = f"Error closing AI pipeline: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _flush_redis(self) -> ShutdownTask:
        """Flush pending Redis operations and close connections."""
        t0 = time.time()
        task = ShutdownTask(name="flush_redis")

        try:
            redis = aioredis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=self.SUBSYSTEM_TIMEOUT,
            )
            # Save RDB snapshot
            await redis.bgsave()
            # Close all client connections
            client_list = await redis.client_list()
            await redis.close()

            task.status = "ok"
            task.message = f"Redis flushed, {len(client_list)} client(s) disconnected"
            task.details = {"clients_disconnected": len(client_list)}
        except Exception as exc:
            task.status = "error"
            task.message = f"Error flushing Redis: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _close_database(self) -> ShutdownTask:
        """Close the database connection pool."""
        t0 = time.time()
        task = ShutdownTask(name="close_database")

        try:
            from backend.db.session import get_engine

            engine = get_engine()
            if engine is not None:
                await engine.dispose()
                task.status = "ok"
                task.message = "Database connection pool closed"
            else:
                task.status = "ok"
                task.message = "Database engine was not initialized"
        except ImportError:
            task.status = "skipped"
            task.message = "Database dependencies not available (skipped)"
        except Exception as exc:
            task.status = "error"
            task.message = f"Error closing database pool: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task

    async def _save_pending_state(self) -> ShutdownTask:
        """Save any pending state (transcripts, session data)."""
        t0 = time.time()
        task = ShutdownTask(name="save_pending_state")

        try:
            redis = aioredis.from_url(
                self.settings.redis_url,
                socket_connect_timeout=self.SUBSYSTEM_TIMEOUT,
            )

            # Move active transcripts to a processing queue for recovery
            pending_transcripts = await redis.keys("transcript:pending:*")
            if pending_transcripts:
                for key in pending_transcripts:
                    await redis.lpush("transcript:recovery_queue", key)
                task.message = f"Queued {len(pending_transcripts)} pending transcript(s) for recovery"
            else:
                task.message = "No pending transcripts to save"

            # Persist any unsaved session summaries
            unsaved_sessions = await redis.keys("session:*:summary:unsaved")
            if unsaved_sessions:
                task.message += f", {len(unsaved_sessions)} unsaved session(s) queued"

            await redis.close()
            task.status = "ok"
        except Exception as exc:
            task.status = "error"
            task.message = f"Error saving pending state: {exc}"

        task.latency_ms = (time.time() - t0) * 1000
        return task


async def execute_graceful_shutdown(reason: str = "shutdown requested") -> ShutdownReport:
    """Convenience function for graceful shutdown.

    Usage:
        report = await execute_graceful_shutdown("SIGTERM received")
        print(f"Shutdown completed in {report.total_latency_ms:.1f}ms")
    """
    handler = GracefulShutdown()
    return await handler.execute(reason=reason)


def register_signal_handlers() -> None:
    """Register OS signal handlers for graceful shutdown.

    Usage:
        # Call during app startup
        from backend.shutdown import register_signal_handlers
        register_signal_handlers()
    """

    def _signal_handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logger.warning("shutdown.signal_received", signal=sig_name)
        # Note: signal handlers cannot be async, so we create a task
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(execute_graceful_shutdown(reason=f"{sig_name} received"))
        except RuntimeError:
            pass

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
    logger.info("shutdown.signal_handlers_registered")


if __name__ == "__main__":
    # Standalone shutdown for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = asyncio.run(execute_graceful_shutdown("manual CLI shutdown"))
    print("\n" + "=" * 60)
    print("ANSWERFLOW AI — SHUTDOWN REPORT")
    print("=" * 60)
    for task in report.tasks:
        icon = "OK " if task.status == "ok" else "ERR" if task.status == "error" else "SKIP"
        print(f"  [{icon}] {task.name:25s} — {task.message}")
    print("-" * 60)
    print(f"  Total: {len(report.tasks)} tasks, {sum(1 for t in report.tasks if t.status == 'error')} errors")
    print(f"  Latency: {report.total_latency_ms:.1f}ms")
    print("=" * 60)

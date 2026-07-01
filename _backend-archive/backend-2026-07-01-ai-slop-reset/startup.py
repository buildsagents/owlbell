"""
Owlbell — Startup Validation.

Location: backend/startup.py

Validates all external dependencies at application startup:
1. Required environment variables
2. Database connectivity (PostgreSQL)
3. Redis connectivity (cache, pub/sub, sessions)
4. FreeSWITCH connectivity (ESL)
5. AI model availability (Whisper, Ollama, Piper)

Usage:
    from backend.startup import StartupValidator
    validator = StartupValidator()
    report = await validator.validate_all()
    if not report.is_healthy:
        logger.error(f"Startup failed: {report.errors}")
        sys.exit(1)

Called from the FastAPI lifespan context manager in app_factory.py.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
import asyncpg
import redis.asyncio as aioredis

from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class ServiceCheck:
    """Result of a single service health check."""

    name: str
    status: str  # "ok" | "error" | "warning"
    latency_ms: float = 0.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return self.status == "ok"


@dataclass
class StartupReport:
    """Aggregated startup validation report."""

    checks: List[ServiceCheck] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    @property
    def is_healthy(self) -> bool:
        return all(c.is_ok for c in self.checks)

    @property
    def total_latency_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000

    @property
    def errors(self) -> List[str]:
        return [f"{c.name}: {c.message}" for c in self.checks if not c.is_ok]

    @property
    def warnings(self) -> List[str]:
        return [f"{c.name}: {c.message}" for c in self.checks if c.status == "warning"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.is_healthy,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status,
                    "latency_ms": round(c.latency_ms, 2),
                    "message": c.message,
                    "details": c.details,
                }
                for c in self.checks
            ],
        }


class StartupValidator:
    """Validates all external dependencies at application startup."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.report = StartupReport()

    async def validate_all(self) -> StartupReport:
        """Run all startup validation checks concurrently.

        Returns a StartupReport with the status of all dependencies.
        """
        self.report.start_time = time.time()
        logger.info("startup.validation_start")

        # Run all checks concurrently
        results = await asyncio.gather(
            self._check_environment_variables(),
            self._check_database(),
            self._check_redis(),
            self._check_freeswitch(),
            self._check_whisper(),
            self._check_ollama(),
            self._check_piper(),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, Exception):
                self.report.checks.append(
                    ServiceCheck(
                        name="unknown",
                        status="error",
                        message=f"Unexpected error: {result}",
                    )
                )
            else:
                self.report.checks.append(result)

        self.report.end_time = time.time()

        if self.report.is_healthy:
            logger.info(
                "startup.validation_complete",
                total_ms=round(self.report.total_latency_ms, 2),
                checks=len(self.report.checks),
            )
        else:
            logger.error(
                "startup.validation_failed",
                errors=self.report.errors,
                total_ms=round(self.report.total_latency_ms, 2),
            )

        return self.report

    async def _check_environment_variables(self) -> ServiceCheck:
        """Verify required environment variables are set."""
        t0 = time.time()
        check = ServiceCheck(name="environment_variables")
        required_vars = [
            ("POSTGRES_PASSWORD", "Database password"),
            ("SECURITY_JWT_SECRET", "JWT signing secret"),
        ]
        missing = []
        for var_name, description in required_vars:
            value = getattr(self.settings.security, "jwt_secret", None)
            if var_name == "POSTGRES_PASSWORD":
                pw = self.settings.database.password
                if pw and pw.get_secret_value() == "answerflow":
                    missing.append(f"{var_name} (using default)")
            elif var_name == "SECURITY_JWT_SECRET":
                if not value or value.get_secret_value() == "":
                    missing.append(f"{var_name} (empty)")

        latency = (time.time() - t0) * 1000
        check.latency_ms = latency

        if missing:
            check.status = "warning"
            check.message = f"Using default values for: {', '.join(missing)}"
            check.details = {"missing": missing}
        else:
            check.status = "ok"
            check.message = "All required environment variables are set"

        return check

    async def _check_database(self) -> ServiceCheck:
        """Verify PostgreSQL connectivity."""
        t0 = time.time()
        check = ServiceCheck(name="database")

        try:
            conn = await asyncpg.connect(
                host=self.settings.database.host,
                port=self.settings.database.port,
                user=self.settings.database.user,
                password=self.settings.database.password.get_secret_value(),
                database=self.settings.database.db,
                timeout=5.0,
            )
            version = await conn.fetchval("SELECT version()")
            await conn.close()

            check.status = "ok"
            check.message = f"PostgreSQL connected: {version[:50]}..."
            check.details = {
                "host": self.settings.database.host,
                "port": self.settings.database.port,
                "database": self.settings.database.db,
                "version": version[:50],
            }
        except Exception as exc:
            check.status = "error"
            check.message = f"PostgreSQL connection failed: {exc}"
            check.details = {
                "host": self.settings.database.host,
                "port": self.settings.database.port,
            }

        check.latency_ms = (time.time() - t0) * 1000
        return check

    async def _check_redis(self) -> ServiceCheck:
        """Verify Redis connectivity."""
        t0 = time.time()
        check = ServiceCheck(name="redis")

        try:
            redis = aioredis.from_url(
                self.settings.redis.url,
                socket_connect_timeout=5.0,
                socket_keepalive=True,
                health_check_interval=30,
            )
            pong = await redis.ping()
            info = await redis.info("server")
            await redis.close()

            check.status = "ok" if pong else "error"
            check.message = (
                f"Redis connected: v{info.get('redis_version', 'unknown')}"
                if pong
                else "Redis ping failed"
            )
            check.details = {
                "host": self.settings.redis.host,
                "port": self.settings.redis.port,
                "version": info.get("redis_version", "unknown"),
            }
        except Exception as exc:
            check.status = "error"
            check.message = f"Redis connection failed: {exc}"
            check.details = {
                "host": self.settings.redis.host,
                "port": self.settings.redis.port,
            }

        check.latency_ms = (time.time() - t0) * 1000
        return check

    async def _check_freeswitch(self) -> ServiceCheck:
        """Verify FreeSWITCH ESL connectivity."""
        t0 = time.time()
        check = ServiceCheck(name="freeswitch")

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.settings.freeswitch.host,
                    self.settings.freeswitch.esl_port,
                ),
                timeout=3.0,
            )
            writer.close()
            await writer.wait_closed()

            check.status = "ok"
            check.message = f"FreeSWITCH ESL port reachable on {self.settings.freeswitch.host}:{self.settings.freeswitch.esl_port}"
            check.details = {
                "host": self.settings.freeswitch.host,
                "esl_port": self.settings.freeswitch.esl_port,
                "sip_port": self.settings.freeswitch.sip_port,
            }
        except asyncio.TimeoutError:
            check.status = "warning"
            check.message = f"FreeSWITCH ESL connection timed out ({self.settings.freeswitch.host}:{self.settings.freeswitch.esl_port})"
            check.details = {"host": self.settings.freeswitch.host}
        except Exception as exc:
            check.status = "warning"
            check.message = f"FreeSWITCH not reachable: {exc}"
            check.details = {"host": self.settings.freeswitch.host}

        check.latency_ms = (time.time() - t0) * 1000
        return check

    async def _check_whisper(self) -> ServiceCheck:
        """Verify Whisper STT service availability."""
        t0 = time.time()
        check = ServiceCheck(name="whisper_stt")

        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"http://{self.settings.ai.whisper.service_host}:{self.settings.ai.whisper.service_port}/health"
                ) as resp:
                    check.status = "ok" if resp.status == 200 else "warning"
                    check.message = f"Whisper STT: HTTP {resp.status}"
        except aiohttp.ClientConnectorError:
            check.status = "warning"
            check.message = (
                f"Whisper STT not running at "
                f"{self.settings.ai.whisper.service_host}:{self.settings.ai.whisper.service_port}"
            )
        except Exception as exc:
            check.status = "warning"
            check.message = f"Whisper STT check failed: {exc}"

        check.latency_ms = (time.time() - t0) * 1000
        check.details = {
            "host": self.settings.ai.whisper.service_host,
            "port": self.settings.ai.whisper.service_port,
            "model": self.settings.ai.whisper.model_size,
        }
        return check

    async def _check_ollama(self) -> ServiceCheck:
        """Verify Ollama LLM service availability."""
        t0 = time.time()
        check = ServiceCheck(name="ollama_llm")

        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{self.settings.ai.ollama.base_url}/api/tags"
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = [m.get("name", "") for m in data.get("models", [])]
                        target = self.settings.ai.ollama.model
                        check.status = "ok" if target in models else "warning"
                        check.message = (
                            f"Ollama running, model '{target}' available"
                            if target in models
                            else f"Ollama running, model '{target}' NOT loaded. Available: {models[:5]}"
                        )
                        check.details = {
                            "host": self.settings.ai.ollama.host,
                            "port": self.settings.ai.ollama.port,
                            "model": target,
                            "available_models": models[:10],
                        }
                    else:
                        check.status = "warning"
                        check.message = f"Ollama: HTTP {resp.status}"
        except aiohttp.ClientConnectorError:
            check.status = "warning"
            check.message = (
                f"Ollama not running at "
                f"{self.settings.ai.ollama.host}:{self.settings.ai.ollama.port}"
            )
        except Exception as exc:
            check.status = "warning"
            check.message = f"Ollama check failed: {exc}"

        check.latency_ms = (time.time() - t0) * 1000
        return check

    async def _check_piper(self) -> ServiceCheck:
        """Verify Piper TTS service availability."""
        t0 = time.time()
        check = ServiceCheck(name="piper_tts")

        try:
            timeout = aiohttp.ClientTimeout(total=5.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"http://{self.settings.ai.piper.service_host}:{self.settings.ai.piper.service_port}/health"
                ) as resp:
                    check.status = "ok" if resp.status == 200 else "warning"
                    check.message = f"Piper TTS: HTTP {resp.status}"
        except aiohttp.ClientConnectorError:
            check.status = "warning"
            check.message = (
                f"Piper TTS not running at "
                f"{self.settings.ai.piper.service_host}:{self.settings.ai.piper.service_port}"
            )
        except Exception as exc:
            check.status = "warning"
            check.message = f"Piper TTS check failed: {exc}"

        check.latency_ms = (time.time() - t0) * 1000
        check.details = {
            "host": self.settings.ai.piper.service_host,
            "port": self.settings.ai.piper.service_port,
            "model": self.settings.ai.piper.model,
        }
        return check


async def run_startup_validation() -> StartupReport:
    """Convenience function to run all startup checks.

    Usage:
        report = await run_startup_validation()
        if not report.is_healthy:
            print("CRITICAL ERRORS:", report.errors)
            sys.exit(1)
    """
    validator = StartupValidator()
    return await validator.validate_all()


if __name__ == "__main__":
    # Standalone startup check for CLI usage
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    report = asyncio.run(run_startup_validation())
    print("\n" + "=" * 60)
    print("ANSWERFLOW AI — STARTUP VALIDATION REPORT")
    print("=" * 60)
    for check in report.checks:
        icon = "OK " if check.is_ok else "ERR" if check.status == "error" else "WARN"
        print(f"  [{icon}] {check.name:25s} — {check.message}")
    print("-" * 60)
    print(f"  Total: {len(report.checks)} checks, {len(report.errors)} errors, {len(report.warnings)} warnings")
    print(f"  Latency: {report.total_latency_ms:.1f}ms")
    print("=" * 60)
    if not report.is_healthy:
        print("STARTUP FAILED — critical errors detected")
        sys.exit(1)
    else:
        print("STARTUP OK — all systems operational")

"""
Owlbell — Centralized Configuration (pydantic-settings).

Location: backend/config.py

Provides:
- ``Settings``: Single source of truth for all configuration
- Environment-based overrides with sensible defaults
- Database, Redis, FreeSWITCH, AI model, security, and plan configs
- ``get_settings()``: Cached settings singleton for the application

Usage:
    from backend.config import get_settings
    settings = get_settings()
    database_url = settings.database.url

Environment variables are read from ``.env`` files automatically.
All secrets **must** be provided via environment variables —
no hard-coded credentials.
"""

from __future__ import annotations

import logging
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT
ROOT_DIR = BACKEND_DIR.parent
ENV_FILE = ROOT_DIR / ".env"


# ---------------------------------------------------------------------------
# Settings classes
# ---------------------------------------------------------------------------


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration (Supabase-hosted)."""

    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Direct connection URL (Supabase pooler) — takes precedence if set
    database_url: Optional[str] = Field(default=None, validation_alias="DATABASE_URL")

    # Individual vars (fallback if DATABASE_URL not set)
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("")
    db: str = "postgres"

    # Connection pool
    pool_size: int = Field(default=20, validation_alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, validation_alias="DB_POOL_RECYCLE")
    pool_pre_ping: bool = Field(default=True, validation_alias="DB_POOL_PRE_PING")

    # Async driver
    driver: str = "asyncpg"

    @property
    def url(self) -> str:
        """Build async PostgreSQL connection URL. Uses DATABASE_URL if set."""
        import os
        db_url = self.database_url or os.environ.get("DATABASE_URL")
        if db_url:
            # Ensure asyncpg driver prefix
            url = db_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", f"postgresql+{self.driver}://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", f"postgresql+{self.driver}://", 1)
            return url
        pw = self.password.get_secret_value()
        return (
            f"postgresql+{self.driver}://"
            f"{self.user}:{pw}@{self.host}:{self.port}/{self.db}"
        )

    @property
    def sync_url(self) -> str:
        """Build synchronous PostgreSQL connection URL (for Alembic)."""
        import os
        db_url = self.database_url or os.environ.get("DATABASE_URL")
        if db_url:
            url = db_url
            if url.startswith("postgresql+asyncpg://"):
                url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
            elif url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        pw = self.password.get_secret_value()
        return f"postgresql://{self.user}:{pw}@{self.host}:{self.port}/{self.db}"


class RedisSettings(BaseSettings):
    """Redis configuration for caching, sessions, pub/sub, and Celery broker."""

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        extra="ignore",
    )

    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[SecretStr] = None
    user: Optional[str] = None
    ssl: bool = Field(default=False, alias="REDIS_SSL")

    # Connection
    connection_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    socket_keepalive: bool = True
    health_check_interval: int = 30

    @property
    def url(self) -> str:
        """Build Redis connection URL. Uses REDIS_URL if set (Railway plugin)."""
        if self.redis_url:
            return self.redis_url
        scheme = "rediss" if self.ssl else "redis"
        creds = ""
        if self.password:
            pw = self.password.get_secret_value()
            creds = f"{self.user}:{pw}@" if self.user else f":{pw}@"
        return f"{scheme}://{creds}{self.host}:{self.port}/{self.db}"

    @property
    def broker_url(self) -> str:
        """Celery broker URL (same as Redis URL)."""
        return self.url

    @property
    def backend_url(self) -> str:
        """Celery result backend URL (same as Redis URL with DB 1)."""
        if self.redis_url:
            return self.redis_url
        scheme = "rediss" if self.ssl else "redis"
        creds = ""
        if self.password:
            pw = self.password.get_secret_value()
            creds = f"{self.user}:{pw}@" if self.user else f":{pw}@"
        return f"{scheme}://{creds}{self.host}:{self.port}/1"


class FreeSWITCHSettings(BaseSettings):
    """FreeSWITCH telephony server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="FS_",
        extra="ignore",
    )

    host: str = "localhost"
    esl_port: int = 8021
    esl_password: SecretStr = SecretStr("ClueCon")
    sip_port: int = 5060
    sip_tls_port: int = 5061
    ws_port: int = 5066
    wss_port: int = 7443
    rtp_port_min: int = 16384
    rtp_port_max: int = 32768
    event_socket_timeout: float = 10.0

    # Retry / circuit breaker
    connection_retries: int = 5
    retry_backoff_base: float = 1.5
    max_retry_delay: float = 30.0


class WhisperSettings(BaseSettings):
    """OpenAI Whisper STT configuration."""

    model_config = SettingsConfigDict(
        env_prefix="WHISPER_",
        extra="ignore",
        protected_namespaces=(),  # allow ``model_size`` without pydantic warning
    )

    model_size: str = "base"
    language: str = "en"
    device: str = "cpu"
    compute_type: str = "int8"
    beam_size: int = 5
    best_of: int = 5
    patience: float = 1.0
    condition_on_previous_text: bool = True
    vad_filter: bool = True
    vad_parameters_min_silence_duration_ms: int = 500
    vad_parameters_speech_pad_ms: int = 300

    # Connection
    service_host: str = "localhost"
    service_port: int = 8001
    service_url: Optional[str] = None
    request_timeout: float = 10.0

    @field_validator("service_url", mode="before")
    @classmethod
    def build_url(cls, v: Optional[str], info: Any) -> str:
        if v:
            return v
        values = info.data
        host = values.get("service_host", "localhost")
        port = values.get("service_port", 8001)
        return f"http://{host}:{port}/v1/audio/transcriptions"


class OllamaSettings(BaseSettings):
    """Ollama LLM configuration."""

    model_config = SettingsConfigDict(
        env_prefix="OLLAMA_",
        extra="ignore",
    )

    host: str = "localhost"
    port: int = 11434
    model: str = "llama3.2:3b"
    fallback_model: str = "phi3:mini"
    embedding_model: str = "nomic-embed-text"
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 40
    repeat_penalty: float = 1.1
    system_prompt: str = (
        "You are Owlbell, a professional phone answering assistant. "
        "Be concise, helpful, and courteous. Keep responses under 3 sentences "
        "when possible."
    )

    # Connection
    request_timeout: float = 30.0
    keep_alive: str = "5m"
    num_ctx: int = 4096
    num_predict: int = 512

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/generate"

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    @property
    def embedding_url(self) -> str:
        return f"{self.base_url}/api/embeddings"


class PiperSettings(BaseSettings):
    """Piper TTS configuration."""

    model_config = SettingsConfigDict(
        env_prefix="PIPER_",
        extra="ignore",
    )

    model: str = "en_US-lessac-medium"
    speaker_id: Optional[int] = None
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w: float = 0.8
    sentence_silence: float = 0.2
    sample_rate: int = 22050
    audio_format: str = "wav"

    # Connection
    service_host: str = "localhost"
    service_port: int = 8002
    service_url: Optional[str] = None
    request_timeout: float = 10.0

    @field_validator("service_url", mode="before")
    @classmethod
    def build_url(cls, v: Optional[str], info: Any) -> str:
        if v:
            return v
        values = info.data
        host = values.get("service_host", "localhost")
        port = values.get("service_port", 8002)
        return f"http://{host}:{port}/synthesize"


class AIServiceSettings(BaseSettings):
    """Aggregated AI service configuration."""

    whisper: WhisperSettings = Field(default_factory=WhisperSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    piper: PiperSettings = Field(default_factory=PiperSettings)

    # Pipeline tuning
    max_turns_per_call: int = 100
    max_call_duration_minutes: int = 60
    silence_timeout_seconds: float = 5.0
    max_greeting_duration_seconds: float = 8.0


class SecuritySettings(BaseSettings):
    """Security configuration — JWT, passwords, rate limits."""

    model_config = SettingsConfigDict(
        env_prefix="SECURITY_",
        extra="ignore",
    )

    jwt_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(32)),
        validation_alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 60
    jwt_refresh_token_ttl_days: int = 7
    jwt_magic_link_ttl_minutes: int = 15

    password_hash_rounds: int = 12
    api_key_prefix: str = "af_"
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    require_email_verification: bool = False
    allowed_hosts: List[str] = Field(default_factory=lambda: ["*"])
    cors_origins_str: str = Field(default="*", validation_alias="SECURITY_CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        return [x.strip() for x in self.cors_origins_str.split(",") if x.strip()]

    # Rate limits (per minute)
    rate_limit_anon_per_minute: int = 30
    rate_limit_auth_per_minute: int = 120
    rate_limit_api_per_minute: int = 300


class CelerySettings(BaseSettings):
    """Celery distributed task queue configuration."""

    model_config = SettingsConfigDict(
        env_prefix="CELERY_",
        extra="ignore",
    )

    broker_url: Optional[str] = None
    result_backend: Optional[str] = None
    worker_concurrency: int = 4
    worker_prefetch_multiplier: int = 1
    task_soft_time_limit: int = 60
    task_time_limit: int = 120
    task_acks_late: bool = True
    task_track_started: bool = True
    task_serializer: str = "json"
    accept_content: List[str] = Field(default_factory=lambda: ["json"])
    result_serializer: str = "json"
    timezone: str = "UTC"
    enable_utc: bool = True
    beat_schedule: Optional[Dict[str, Any]] = None

    # Queues
    default_queue: str = "default"
    ai_queue: str = "ai"
    notifications_queue: str = "notifications"
    sync_queue: str = "sync"


class PlanLimitSettings(BaseSettings):
    """Plan-based usage limits and feature gating."""

    model_config = SettingsConfigDict(
        env_prefix="PLAN_",
        extra="ignore",
    )

    free_max_calls_monthly: int = 100
    free_max_users: int = 2
    free_max_minutes_monthly: int = 300
    free_ai_model_tier: str = "fast"

    starter_max_calls_monthly: int = 500
    starter_max_users: int = 5
    starter_max_minutes_monthly: int = 2000
    starter_ai_model_tier: str = "quality"

    pro_max_calls_monthly: int = 2000
    pro_max_users: int = 20
    pro_max_minutes_monthly: int = 10000
    pro_ai_model_tier: str = "premium"

    enterprise_max_calls_monthly: int = 0  # 0 = unlimited
    enterprise_max_users: int = 0
    enterprise_max_minutes_monthly: int = 0
    enterprise_ai_model_tier: str = "premium"

    @property
    def limits(self) -> Dict[str, Dict[str, Any]]:
        """Return all plan limits as a nested dict."""
        return {
            "free": {
                "max_calls_monthly": self.free_max_calls_monthly,
                "max_users": self.free_max_users,
                "max_minutes_monthly": self.free_max_minutes_monthly,
                "ai_model_tier": self.free_ai_model_tier,
            },
            "starter": {
                "max_calls_monthly": self.starter_max_calls_monthly,
                "max_users": self.starter_max_users,
                "max_minutes_monthly": self.starter_max_minutes_monthly,
                "ai_model_tier": self.starter_ai_model_tier,
            },
            "pro": {
                "max_calls_monthly": self.pro_max_calls_monthly,
                "max_users": self.pro_max_users,
                "max_minutes_monthly": self.pro_max_minutes_monthly,
                "ai_model_tier": self.pro_ai_model_tier,
            },
            "enterprise": {
                "max_calls_monthly": self.enterprise_max_calls_monthly,
                "max_users": self.enterprise_max_users,
                "max_minutes_monthly": self.enterprise_max_minutes_monthly,
                "ai_model_tier": self.enterprise_ai_model_tier,
            },
        }


class MonitoringSettings(BaseSettings):
    """Monitoring, logging, and alerting configuration."""

    model_config = SettingsConfigDict(
        env_prefix="MONITOR_",
        extra="ignore",
    )

    log_level: str = "INFO"
    log_format: str = "json"  # "json" | "text"
    enable_structlog: bool = True
    enable_prometheus: bool = True
    prometheus_port: int = 9090
    sentry_dsn: Optional[SecretStr] = None
    health_check_timeout: float = 5.0

    # Alert thresholds
    alert_cpu_threshold: float = 85.0
    alert_memory_threshold: float = 85.0
    alert_disk_threshold: float = 90.0
    alert_call_drop_rate: float = 5.0


class FeatureFlagsSettings(BaseSettings):
    """Feature flags and toggles."""

    model_config = SettingsConfigDict(
        env_prefix="FEATURE_",
        extra="ignore",
    )

    enable_call_transcription: bool = True
    enable_ai_greeting: bool = True
    enable_smart_routing: bool = True
    enable_callback_scheduling: bool = True
    enable_voicemail_ai: bool = True
    enable_real_time_dashboard: bool = True
    enable_webhook_events: bool = True
    enable_sms_notifications: bool = True
    enable_email_notifications: bool = True
    enable_calendar_sync: bool = True
    enable_crm_sync: bool = True
    enable_ab_testing: bool = False
    enable_gradual_rollout: bool = False


class IntegrationSettings(BaseSettings):
    """Third-party integration settings."""

    model_config = SettingsConfigDict(
        env_prefix="INTEGRATION_",
        extra="ignore",
    )

    # Twilio (primary telephony provider — phone numbers + SIP trunk to Retell AI)
    twilio_account_sid: Optional[SecretStr] = None
    twilio_auth_token: Optional[SecretStr] = None
    twilio_from_number: Optional[str] = None
    twilio_sip_trunk_sid: Optional[str] = None
    twilio_sip_trunk_termination_uri: Optional[str] = None

    # SendGrid (for email)
    sendgrid_api_key: Optional[SecretStr] = None
    sendgrid_from_email: str = "noreply@owlbell.xyz"
    sendgrid_from_name: str = "Owlbell"

    # Slack (for notifications)
    slack_webhook_url: Optional[SecretStr] = None
    slack_channel: str = "#answerflow-alerts"

    # Google (for calendar OAuth)
    google_client_id: Optional[SecretStr] = None
    google_client_secret: Optional[SecretStr] = None
    google_redirect_uri: str = "https://api.owlbell.xyz/api/v1/integrations/google/callback"

    # HubSpot (for CRM)
    hubspot_api_key: Optional[SecretStr] = None
    hubspot_api_url: str = "https://api.hubapi.com"

    # Stripe (for billing / payments)
    stripe_secret_key: Optional[SecretStr] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[SecretStr] = None
    stripe_billing_portal_return_url: str = "https://app.owlbell.xyz/billing"
    stripe_checkout_success_url: str = "https://app.owlbell.xyz/billing?status=success"
    stripe_checkout_cancel_url: str = "https://app.owlbell.xyz/billing?status=cancelled"
    # Recurring price IDs (created by scripts/stripe_setup.py)
    stripe_price_basic_monthly: Optional[str] = None
    stripe_price_basic_annual: Optional[str] = None
    stripe_price_pro_monthly: Optional[str] = None
    stripe_price_pro_annual: Optional[str] = None
    stripe_price_pro_plus_monthly: Optional[str] = None
    stripe_price_pro_plus_annual: Optional[str] = None
    # One-time setup-fee price IDs (optional)
    stripe_price_setup_basic: Optional[str] = None
    stripe_price_setup_pro: Optional[str] = None

    # Retell AI (for phone provisioning and AI agents)
    retell_api_key: Optional[SecretStr] = None
    retell_webhook_secret: Optional[SecretStr] = None

    # Webhook defaults
    webhook_max_retries: int = 3
    webhook_timeout: float = 10.0
    webhook_signature_header: str = "X-Owlbell-Signature"


class Settings(BaseSettings):
    """Root settings class — single source of truth for Owlbell.

    Loads configuration from environment variables and ``.env`` files.
    Nested models group related settings (database, redis, AI, etc.).

    Usage:
        settings = get_settings()
        db_url = settings.database.url
    """

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.exists() else None,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Environment
    env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="APP_DEBUG")
    testing: bool = Field(default=False, alias="APP_TESTING")

    # Application metadata
    app_name: str = "Owlbell"
    app_version: str = "1.0.0"
    app_description: str = "AI-powered 24/7 phone answering service"
    api_prefix: str = "/api/v1"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Subsystem settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    freeswitch: FreeSWITCHSettings = Field(default_factory=FreeSWITCHSettings)
    ai: AIServiceSettings = Field(default_factory=AIServiceSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)
    plans: PlanLimitSettings = Field(default_factory=PlanLimitSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    features: FeatureFlagsSettings = Field(default_factory=FeatureFlagsSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)

    # Static files
    static_dir: Optional[Path] = Field(default=None, alias="STATIC_DIR")
    dashboard_build_dir: Optional[Path] = Field(
        default=None, alias="DASHBOARD_BUILD_DIR"
    )

    @field_validator("static_dir", mode="before")
    @classmethod
    def resolve_static_dir(cls, v: Optional[str]) -> Optional[Path]:
        if v is None:
            return ROOT_DIR / "dashboard" / "dist"
        p = Path(v)
        return p if p.is_absolute() else ROOT_DIR / p

    @field_validator("dashboard_build_dir", mode="before")
    @classmethod
    def resolve_dashboard_dir(cls, v: Optional[str]) -> Optional[Path]:
        if v is None:
            return ROOT_DIR / "dashboard" / "dist"
        p = Path(v)
        return p if p.is_absolute() else ROOT_DIR / p

    @property
    def is_development(self) -> bool:
        return self.env.lower() in ("development", "dev", "local")

    @property
    def is_production(self) -> bool:
        return self.env.lower() in ("production", "prod")

    @property
    def is_testing(self) -> bool:
        return self.testing or self.env.lower() in ("test", "testing")

    @property
    def database_url(self) -> str:
        """Shortcut to database URL."""
        return self.database.url

    @property
    def redis_url(self) -> str:
        """Shortcut to Redis URL."""
        return self.redis.url

    @property
    def celery_broker_url(self) -> str:
        """Celery broker URL (from Redis or explicit override)."""
        return self.celery.broker_url or self.redis.broker_url

    @property
    def celery_backend_url(self) -> str:
        """Celery result backend URL."""
        return self.celery.result_backend or self.redis.backend_url

    def to_health_dict(self) -> Dict[str, Any]:
        """Return a safe subset for health check responses (no secrets)."""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "env": self.env,
            "debug": self.debug,
            "database_host": self.database.host,
            "database_port": self.database.port,
            "database_db": self.database.db,
            "redis_host": self.redis.host,
            "redis_port": self.redis.port,
            "freeswitch_host": self.freeswitch.host,
            "freeswitch_esl_port": self.freeswitch.esl_port,
            "whisper_model": self.ai.whisper.model_size,
            "ollama_model": self.ai.ollama.model,
            "piper_model": self.ai.piper.model,
            "features": {
                "call_transcription": self.features.enable_call_transcription,
                "ai_greeting": self.features.enable_ai_greeting,
                "smart_routing": self.features.enable_smart_routing,
                "calendar_sync": self.features.enable_calendar_sync,
            },
        }


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings singleton.

    The result is cached for the lifetime of the process.
    """
    return Settings()


# Legacy alias for compatibility
settings = get_settings

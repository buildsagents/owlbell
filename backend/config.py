"""Runtime configuration."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    public_site_url: str = Field(default="https://owlbell.xyz", alias="PUBLIC_SITE_URL")
    api_base_url: str = Field(
        default="https://owlbell-api-production.up.railway.app",
        alias="API_BASE_URL",
    )
    cors_origins_raw: str = Field(
        default="https://owlbell.xyz,http://localhost:3000",
        alias="SECURITY_CORS_ORIGINS",
    )
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    redis_url: str | None = Field(default=None, alias="REDIS_URL")

    @property
    def enable_docs(self) -> bool:
        return self.app_env != "production" or self.app_debug

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

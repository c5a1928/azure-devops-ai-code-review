from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_or_create_secret_key() -> str:
    env_value = os.getenv("APP_SECRET_KEY", "").strip()
    if env_value:
        return env_value
    path = Path("data/.secret_key")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(32)
    path.write_text(secret, encoding="utf-8")
    return secret


class InfrastructureSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/code_review"
    app_secret_key: str = ""
    admin_password: str = ""
    keycloak_enabled: bool = True
    keycloak_internal_url: str = "http://localhost:8081"
    keycloak_public_url: str = "http://localhost:8081"
    keycloak_realm: str = "plyrev"
    keycloak_client_id: str = "plyrev-web"

    @field_validator("admin_password", mode="before")
    @classmethod
    def strip_admin_password(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


# Backwards-compatible env names for review settings used only at bootstrap.
class LegacyEnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_devops_base_url: str = "https://dev.azure.com"
    azure_devops_org: str = ""
    azure_devops_project: str = ""
    azure_devops_pat: str = ""
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"
    openai_temperature: float = 0.0
    openai_max_tokens: int = 16384
    openai_reasoning_effort: str | None = "high"
    gmail_user: str = ""
    gmail_app_password: str = ""


@lru_cache
def get_infrastructure_settings() -> InfrastructureSettings:
    settings = InfrastructureSettings()
    if not settings.app_secret_key.strip():
        return settings.model_copy(update={"app_secret_key": _load_or_create_secret_key()})
    return settings


@lru_cache
def get_legacy_env_settings() -> LegacyEnvSettings:
    return LegacyEnvSettings()


# Kept for Celery broker configuration at import time.
@lru_cache
def get_settings() -> LegacyEnvSettings:
    return get_legacy_env_settings()

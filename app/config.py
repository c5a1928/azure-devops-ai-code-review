from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    azure_devops_base_url: str = "https://dev.azure.com"
    azure_devops_org: str
    azure_devops_project: str
    azure_devops_pat: str

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"
    openai_temperature: float = 0.0
    openai_max_tokens: int = 16384
    openai_reasoning_effort: str | None = "high"

    gmail_user: str
    gmail_app_password: str

    @field_validator("openai_reasoning_effort", mode="before")
    @classmethod
    def normalize_reasoning_effort(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized or None
        return value

    @field_validator("gmail_user", mode="before")
    @classmethod
    def strip_gmail_user(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("gmail_app_password", mode="before")
    @classmethod
    def strip_gmail_app_password(cls, value: str) -> str:
        if isinstance(value, str):
            # App passwords are often copied with spaces; Gmail accepts them without.
            return value.strip().replace(" ", "")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()

from __future__ import annotations

from dataclasses import dataclass, replace

from app.services.git.types import GIT_PLATFORMS


@dataclass(frozen=True)
class GitConnectionRuntime:
    id: int
    label: str
    git_platform: str
    git_base_url: str
    git_owner: str
    git_token: str


@dataclass(frozen=True)
class ReviewRuntimeSettings:
    git_platform: str
    git_base_url: str
    git_owner: str
    git_default_project: str
    git_default_repo: str
    git_token: str
    llm_provider: str
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    openai_temperature: float
    openai_max_tokens: int
    openai_reasoning_effort: str | None
    gmail_user: str
    gmail_app_password: str

    def missing_fields(self) -> list[str]:
        key_field = "cursor_api_key" if self.llm_provider == "cursor" else "openai_api_key"
        required: dict[str, str] = {key_field: self.openai_api_key}
        return [name for name, value in required.items() if not str(value).strip()]

    def validate_platform(self) -> None:
        if self.git_platform not in GIT_PLATFORMS:
            raise ValueError(f"Unsupported git platform: {self.git_platform}")

from datetime import datetime

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    pr_id: int = Field(..., ge=1, description="Pull request / merge request ID")
    git_project_id: int = Field(..., ge=1, description="Configured git project ID")


class ReviewResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None


class ReviewJobPublic(BaseModel):
    task_id: str
    git_project_id: int
    display_path: str
    platform: str
    repo_name: str
    pr_id: int
    status: str
    step: str | None = None
    error: str | None = None
    pr_url: str | None = None
    title: str | None = None
    verdict: str | None = None
    result: dict | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    archived_at: datetime | None = None


class AuthLoginRequest(BaseModel):
    password: str = ""


class AuthLoginResponse(BaseModel):
    access_token: str
    auth_required: bool


class KeycloakAuthConfig(BaseModel):
    url: str
    realm: str
    client_id: str


class AuthStatusResponse(BaseModel):
    auth_required: bool
    provider: str = "none"
    keycloak: KeycloakAuthConfig | None = None


class BaseUrlOption(BaseModel):
    label: str
    url: str


class GitPlatformInfo(BaseModel):
    id: str
    name: str
    default_base_url: str
    base_url_options: list[BaseUrlOption]
    owner_label: str
    project_label: str
    repo_label: str
    token_label: str
    project_required: bool
    repo_required: bool = True


class ModelOption(BaseModel):
    label: str
    id: str


class LlmProviderInfo(BaseModel):
    id: str
    name: str
    default_base_url: str
    default_model: str
    base_url_options: list[BaseUrlOption]
    model_options: list[ModelOption]
    token_label: str


class GitProjectCreate(BaseModel):
    git_connection_id: int = Field(..., ge=1)
    label: str = ""
    project: str = ""
    repo: str = ""


class GitProjectUpdate(BaseModel):
    git_connection_id: int = Field(..., ge=1)
    label: str = ""
    project: str = ""
    repo: str = ""


class GitProjectPublic(BaseModel):
    id: int
    git_connection_id: int
    git_connection_label: str
    platform: str
    label: str
    project: str
    repo: str
    display_path: str


class GitConnectionCreate(BaseModel):
    label: str = ""
    platform: str = "azure_devops"
    base_url: str = "https://dev.azure.com"
    owner: str = ""
    token: str = ""


class GitConnectionUpdate(BaseModel):
    label: str = ""
    platform: str = "azure_devops"
    base_url: str = "https://dev.azure.com"
    owner: str = ""
    token: str = ""


class GitConnectionPublic(BaseModel):
    id: int
    label: str
    platform: str
    platform_name: str
    base_url: str
    owner: str
    token_configured: bool
    token_masked: str | None = None
    display_name: str


class ReviewSettingsUpdate(BaseModel):
    git_platform: str = "azure_devops"
    git_base_url: str = "https://dev.azure.com"
    git_owner: str = ""
    git_default_project: str = ""
    git_default_repo: str = ""
    git_token: str = ""
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.5"
    openai_temperature: float = 0.0
    openai_max_tokens: int = 16384
    openai_reasoning_effort: str | None = "high"
    gmail_user: str = ""
    gmail_app_password: str = ""


class ReviewSettingsPublic(BaseModel):
    git_platform: str
    git_base_url: str
    git_owner: str
    git_default_project: str
    git_default_repo: str
    git_token_configured: bool
    git_token_masked: str | None = None
    llm_provider: str
    openai_api_key_configured: bool
    openai_api_key_masked: str | None = None
    openai_base_url: str
    openai_model: str
    openai_temperature: float
    openai_max_tokens: int
    openai_reasoning_effort: str | None
    gmail_user: str
    gmail_app_password_configured: bool
    gmail_app_password_masked: str | None = None
    git_connection_count: int = 0
    git_project_count: int = 0
    configured: bool
    missing_fields: list[str] = Field(default_factory=list)

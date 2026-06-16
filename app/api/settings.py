from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import auth_provider, auth_required, keycloak_public_config, login, require_auth
from app.schemas import (
    AuthLoginRequest,
    AuthLoginResponse,
    AuthStatusResponse,
    BaseUrlOption,
    GitPlatformInfo,
    KeycloakAuthConfig,
    LlmProviderInfo,
    ModelOption,
    ReviewSettingsPublic,
    ReviewSettingsUpdate,
)
from app.services.git.types import GIT_PLATFORMS, PLATFORM_BASE_URL_OPTIONS, PLATFORM_DEFAULTS
from app.services.llm.types import (
    LLM_PROVIDER_BASE_URL_OPTIONS,
    LLM_PROVIDER_DEFAULTS,
    LLM_PROVIDER_MODEL_OPTIONS,
    LLM_PROVIDER_NAMES,
)
from app.settings_store import get_public_settings, update_settings

router = APIRouter(prefix="/api")

_PLATFORM_NAMES = {
    "azure_devops": "Azure DevOps",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
}


@router.get("/auth/status", response_model=AuthStatusResponse)
def auth_status() -> AuthStatusResponse:
    keycloak_config = keycloak_public_config()
    return AuthStatusResponse(
        auth_required=auth_required(),
        provider=auth_provider(),
        keycloak=KeycloakAuthConfig(**keycloak_config) if keycloak_config else None,
    )


@router.post("/auth/login", response_model=AuthLoginResponse)
def auth_login(request: AuthLoginRequest) -> AuthLoginResponse:
    if auth_provider() == "keycloak":
        from fastapi import HTTPException

        raise HTTPException(
            status_code=400,
            detail="Use Keycloak sign-in. Password login is disabled when Keycloak is enabled.",
        )
    token = login(request.password)
    if token is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Invalid password")
    return AuthLoginResponse(access_token=token, auth_required=auth_required())


@router.get("/platforms", response_model=list[GitPlatformInfo])
def list_git_platforms() -> list[GitPlatformInfo]:
    platforms: list[GitPlatformInfo] = []
    for platform_id in sorted(GIT_PLATFORMS):
        meta = PLATFORM_DEFAULTS[platform_id]
        platforms.append(
            GitPlatformInfo(
                id=platform_id,
                name=_PLATFORM_NAMES[platform_id],
                default_base_url=meta["base_url"],
                base_url_options=[
                    BaseUrlOption(label=item["label"], url=item["url"])
                    for item in PLATFORM_BASE_URL_OPTIONS[platform_id]
                ],
                owner_label=meta["owner_label"],
                project_label=meta["project_label"],
                repo_label=meta["repo_label"],
                token_label=meta["token_label"],
                project_required=platform_id == "azure_devops",
                repo_required=True,
            )
        )
    return platforms


@router.get("/llm-providers", response_model=list[LlmProviderInfo])
def list_llm_providers() -> list[LlmProviderInfo]:
    providers: list[LlmProviderInfo] = []
    for provider_id in ("openai", "anthropic", "gemini", "llama", "custom"):
        meta = LLM_PROVIDER_DEFAULTS[provider_id]
        providers.append(
            LlmProviderInfo(
                id=provider_id,
                name=LLM_PROVIDER_NAMES[provider_id],
                default_base_url=meta["base_url"],
                default_model=meta["default_model"],
                base_url_options=[
                    BaseUrlOption(label=item["label"], url=item["url"])
                    for item in LLM_PROVIDER_BASE_URL_OPTIONS[provider_id]
                ],
                model_options=[
                    ModelOption(label=item["label"], id=item["id"])
                    for item in LLM_PROVIDER_MODEL_OPTIONS[provider_id]
                ],
                token_label=meta["token_label"],
            )
        )
    return providers


@router.get("/settings", response_model=ReviewSettingsPublic)
def read_settings() -> ReviewSettingsPublic:
    return get_public_settings()


@router.put("/settings", response_model=ReviewSettingsPublic)
def save_settings(
    payload: ReviewSettingsUpdate,
    _: None = Depends(require_auth),
) -> ReviewSettingsPublic:
    return update_settings(payload)

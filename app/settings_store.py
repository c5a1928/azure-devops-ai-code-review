from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, text

from app.db import db_session, get_engine, init_db
from app.git_connections_store import (
    count_git_connections,
    migrate_git_connection_schema,
    migrate_legacy_git_connections,
)
from app.git_projects_store import count_git_projects, migrate_legacy_git_projects
from app.models import AppSettingsRecord
from app.runtime_settings import ReviewRuntimeSettings
from app.schemas import ReviewSettingsPublic, ReviewSettingsUpdate
from app.services.git.types import GIT_PLATFORMS, PLATFORM_DEFAULTS
from app.services.llm.types import (
    LLM_PROVIDER_DEFAULTS,
    LLM_PROVIDERS,
    infer_llm_provider,
)

SECRET_PLACEHOLDER = "__UNCHANGED__"

_SCHEMA_COLUMNS: dict[str, str] = {
    "llm_provider": "VARCHAR(32) DEFAULT 'openai' NOT NULL",
    "git_platform": "VARCHAR(32) DEFAULT 'azure_devops' NOT NULL",
    "git_base_url": "VARCHAR(512) DEFAULT '' NOT NULL",
    "git_owner": "VARCHAR(255) DEFAULT '' NOT NULL",
    "git_default_project": "VARCHAR(255) DEFAULT '' NOT NULL",
    "git_default_repo": "VARCHAR(255) DEFAULT '' NOT NULL",
    "git_token": "TEXT DEFAULT '' NOT NULL",
}


def _mask_secret(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) <= 4:
        return "••••"
    return f"••••{cleaned[-4:]}"


def migrate_schema() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    if "app_settings" not in inspector.get_table_names():
        init_db()
        return
    existing = {column["name"] for column in inspector.get_columns("app_settings")}
    with engine.begin() as conn:
        for name, definition in _SCHEMA_COLUMNS.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE app_settings ADD COLUMN {name} {definition}"))


def _migrate_legacy_record(record: AppSettingsRecord) -> None:
    if record.git_token.strip():
        return
    if record.azure_devops_pat.strip():
        record.git_platform = "azure_devops"
        record.git_base_url = record.azure_devops_base_url or PLATFORM_DEFAULTS["azure_devops"]["base_url"]
        record.git_owner = record.azure_devops_org
        record.git_default_project = record.azure_devops_project
        record.git_token = record.azure_devops_pat


def _resolve_llm_provider(record: AppSettingsRecord) -> str:
    stored = (record.llm_provider or "").strip()
    inferred = infer_llm_provider(record.openai_base_url, record.openai_model)
    if stored in LLM_PROVIDERS:
        if stored == "openai" and inferred != "openai":
            return inferred
        return stored
    return inferred


def _record_to_runtime(record: AppSettingsRecord) -> ReviewRuntimeSettings:
    platform = record.git_platform or "azure_devops"
    defaults = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS["azure_devops"])
    return ReviewRuntimeSettings(
        git_platform=platform,
        git_base_url=record.git_base_url or defaults["base_url"],
        git_owner=record.git_owner,
        git_default_project=record.git_default_project,
        git_default_repo=record.git_default_repo,
        git_token=record.git_token,
        llm_provider=_resolve_llm_provider(record),
        openai_api_key=record.openai_api_key,
        openai_base_url=record.openai_base_url,
        openai_model=record.openai_model,
        openai_temperature=float(record.openai_temperature),
        openai_max_tokens=int(record.openai_max_tokens),
        openai_reasoning_effort=(record.openai_reasoning_effort or None),
        gmail_user=record.gmail_user,
        gmail_app_password=record.gmail_app_password,
    )


def _record_to_public(record: AppSettingsRecord) -> ReviewSettingsPublic:
    runtime = _record_to_runtime(record)
    missing = list(runtime.missing_fields())
    git_connection_count = count_git_connections()
    git_project_count = count_git_projects()
    if git_connection_count == 0:
        missing.append("git_connections")
    if git_project_count == 0:
        missing.append("git_projects")
    return ReviewSettingsPublic(
        git_platform=runtime.git_platform,
        git_base_url=runtime.git_base_url,
        git_owner=runtime.git_owner,
        git_default_project=runtime.git_default_project,
        git_default_repo=runtime.git_default_repo,
        git_token_configured=bool(record.git_token.strip()),
        git_token_masked=_mask_secret(record.git_token),
        llm_provider=_resolve_llm_provider(record),
        openai_api_key_configured=bool(record.openai_api_key.strip()),
        openai_api_key_masked=_mask_secret(record.openai_api_key),
        openai_base_url=record.openai_base_url,
        openai_model=record.openai_model,
        openai_temperature=float(record.openai_temperature),
        openai_max_tokens=int(record.openai_max_tokens),
        openai_reasoning_effort=(record.openai_reasoning_effort or None),
        gmail_user=record.gmail_user,
        gmail_app_password_configured=bool(record.gmail_app_password.strip()),
        gmail_app_password_masked=_mask_secret(record.gmail_app_password),
        git_project_count=git_project_count,
        git_connection_count=git_connection_count,
        configured=len(missing) == 0,
        missing_fields=missing,
    )


def _env_defaults() -> dict[str, Any]:
    import os

    platform = os.getenv("GIT_PLATFORM", "azure_devops")
    defaults = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS["azure_devops"])
    return {
        "git_platform": platform,
        "git_base_url": os.getenv("GIT_BASE_URL", defaults["base_url"]),
        "git_owner": os.getenv("GIT_OWNER", os.getenv("AZURE_DEVOPS_ORG", "")),
        "git_default_project": os.getenv(
            "GIT_DEFAULT_PROJECT", os.getenv("AZURE_DEVOPS_PROJECT", "")
        ),
        "git_default_repo": os.getenv("GIT_DEFAULT_REPO", ""),
        "git_token": os.getenv("GIT_TOKEN", os.getenv("AZURE_DEVOPS_PAT", "")),
        "azure_devops_base_url": os.getenv("AZURE_DEVOPS_BASE_URL", defaults["base_url"]),
        "azure_devops_org": os.getenv("AZURE_DEVOPS_ORG", ""),
        "azure_devops_project": os.getenv("AZURE_DEVOPS_PROJECT", ""),
        "azure_devops_pat": os.getenv("AZURE_DEVOPS_PAT", ""),
        "llm_provider": os.getenv("LLM_PROVIDER", "openai"),
        "openai_api_key": os.getenv("OPENAI_API_KEY", ""),
        "openai_base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "openai_model": os.getenv("OPENAI_MODEL", "gpt-5.5"),
        "openai_temperature": os.getenv("OPENAI_TEMPERATURE", "0.0"),
        "openai_max_tokens": os.getenv("OPENAI_MAX_TOKENS", "16384"),
        "openai_reasoning_effort": os.getenv("OPENAI_REASONING_EFFORT", "high"),
        "gmail_user": os.getenv("GMAIL_USER", ""),
        "gmail_app_password": os.getenv("GMAIL_APP_PASSWORD", ""),
    }


def _get_or_create_record(session) -> AppSettingsRecord:
    record = session.get(AppSettingsRecord, 1)
    if record is None:
        defaults = _env_defaults()
        record = AppSettingsRecord(id=1, **defaults)
        session.add(record)
        session.commit()
        session.refresh(record)
    _migrate_legacy_record(record)
    if record.git_platform not in GIT_PLATFORMS:
        record.git_platform = "azure_devops"
    return record


def bootstrap_settings() -> None:
    migrate_schema()
    init_db()
    migrate_git_connection_schema()
    migrate_legacy_git_connections()
    migrate_legacy_git_projects()
    from app.review_jobs_store import ensure_jobs_table

    ensure_jobs_table()
    with db_session() as session:
        record = _get_or_create_record(session)
        session.add(record)
        session.commit()


def get_public_settings() -> ReviewSettingsPublic:
    with db_session() as session:
        record = _get_or_create_record(session)
        return _record_to_public(record)


def get_runtime_settings() -> ReviewRuntimeSettings:
    with db_session() as session:
        record = _get_or_create_record(session)
        runtime = _record_to_runtime(record)
        runtime.validate_platform()
        return runtime


def update_settings(payload: ReviewSettingsUpdate) -> ReviewSettingsPublic:
    platform = payload.git_platform if payload.git_platform in GIT_PLATFORMS else "azure_devops"
    defaults = PLATFORM_DEFAULTS[platform]
    llm_provider = payload.llm_provider if payload.llm_provider in LLM_PROVIDERS else "openai"
    with db_session() as session:
        record = _get_or_create_record(session)
        record.git_platform = platform
        record.llm_provider = llm_provider
        record.git_base_url = (payload.git_base_url or defaults["base_url"]).strip()
        record.git_owner = payload.git_owner.strip()
        record.git_default_project = payload.git_default_project.strip()
        record.git_default_repo = payload.git_default_repo.strip()
        record.openai_base_url = payload.openai_base_url.strip()
        record.openai_model = payload.openai_model.strip()
        record.openai_temperature = str(payload.openai_temperature)
        record.openai_max_tokens = str(payload.openai_max_tokens)
        record.openai_reasoning_effort = (payload.openai_reasoning_effort or "").strip()
        record.gmail_user = payload.gmail_user.strip()

        if payload.git_token and payload.git_token != SECRET_PLACEHOLDER:
            record.git_token = payload.git_token.strip()
            if platform == "azure_devops":
                record.azure_devops_pat = record.git_token
                record.azure_devops_org = record.git_owner
                record.azure_devops_project = record.git_default_project
                record.azure_devops_base_url = record.git_base_url
        if payload.openai_api_key and payload.openai_api_key != SECRET_PLACEHOLDER:
            record.openai_api_key = payload.openai_api_key.strip()
        if payload.gmail_app_password and payload.gmail_app_password != SECRET_PLACEHOLDER:
            record.gmail_app_password = payload.gmail_app_password.strip().replace(" ", "")

        session.add(record)
        session.commit()
        session.refresh(record)
        return _record_to_public(record)

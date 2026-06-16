from __future__ import annotations

from sqlalchemy import inspect, text

from app.db import db_session, get_engine, init_db
from app.models import AppSettingsRecord, GitConnectionRecord, GitProjectRecord
from app.runtime_settings import GitConnectionRuntime
from app.schemas import GitConnectionCreate, GitConnectionPublic, GitConnectionUpdate
from app.services.git.types import GIT_PLATFORMS, PLATFORM_DEFAULTS

SECRET_PLACEHOLDER = "__UNCHANGED__"

_PLATFORM_NAMES = {
    "azure_devops": "Azure DevOps",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
}


def _mask_secret(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) <= 4:
        return "••••"
    return f"••••{cleaned[-4:]}"


def _connection_display_name(record: GitConnectionRecord) -> str:
    platform_name = _PLATFORM_NAMES.get(record.platform, record.platform)
    label = record.label.strip()
    owner = record.owner.strip()
    if label:
        return f"{label} ({platform_name})"
    if owner:
        return f"{platform_name} — {owner}"
    return platform_name


def _to_public(record: GitConnectionRecord) -> GitConnectionPublic:
    return GitConnectionPublic(
        id=record.id,
        label=record.label,
        platform=record.platform,
        platform_name=_PLATFORM_NAMES.get(record.platform, record.platform),
        base_url=record.base_url,
        owner=record.owner,
        token_configured=bool(record.token.strip()),
        token_masked=_mask_secret(record.token),
        display_name=_connection_display_name(record),
    )


def _to_runtime(record: GitConnectionRecord) -> GitConnectionRuntime:
    platform = record.platform if record.platform in GIT_PLATFORMS else "azure_devops"
    defaults = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS["azure_devops"])
    return GitConnectionRuntime(
        id=record.id,
        label=record.label,
        git_platform=platform,
        git_base_url=record.base_url or defaults["base_url"],
        git_owner=record.owner,
        git_token=record.token,
    )


def migrate_git_connection_schema() -> None:
    init_db()
    engine = get_engine()
    inspector = inspect(engine)
    if "git_projects" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("git_projects")}
    if "git_connection_id" not in existing:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE git_projects ADD COLUMN git_connection_id INTEGER"))


def migrate_legacy_git_connections() -> None:
    with db_session() as session:
        if session.query(GitConnectionRecord).count() > 0:
            return
        record = session.get(AppSettingsRecord, 1)
        if record is None:
            return
        if not record.git_owner.strip() and not record.git_token.strip():
            return
        platform = record.git_platform if record.git_platform in GIT_PLATFORMS else "azure_devops"
        defaults = PLATFORM_DEFAULTS.get(platform, PLATFORM_DEFAULTS["azure_devops"])
        connection = GitConnectionRecord(
            label="",
            platform=platform,
            base_url=record.git_base_url or defaults["base_url"],
            owner=record.git_owner,
            token=record.git_token,
        )
        session.add(connection)
        session.commit()
        session.refresh(connection)

        projects = session.query(GitProjectRecord).all()
        for project in projects:
            if project.git_connection_id is None:
                project.git_connection_id = connection.id
                session.add(project)
        session.commit()


def count_git_connections() -> int:
    with db_session() as session:
        return session.query(GitConnectionRecord).count()


def list_git_connections() -> list[GitConnectionPublic]:
    with db_session() as session:
        records = session.query(GitConnectionRecord).order_by(GitConnectionRecord.id).all()
        return [_to_public(record) for record in records]


def get_git_connection(connection_id: int) -> GitConnectionPublic | None:
    with db_session() as session:
        record = session.get(GitConnectionRecord, connection_id)
        if record is None:
            return None
        return _to_public(record)


def get_git_connection_runtime(connection_id: int) -> GitConnectionRuntime | None:
    with db_session() as session:
        record = session.get(GitConnectionRecord, connection_id)
        if record is None:
            return None
        return _to_runtime(record)


def create_git_connection(payload: GitConnectionCreate) -> GitConnectionPublic:
    platform = payload.platform if payload.platform in GIT_PLATFORMS else "azure_devops"
    defaults = PLATFORM_DEFAULTS[platform]
    owner = payload.owner.strip()
    token = payload.token.strip()
    if not owner:
        raise ValueError("Organization or owner is required.")
    if not token:
        raise ValueError("Access token is required.")
    with db_session() as session:
        record = GitConnectionRecord(
            label=payload.label.strip(),
            platform=platform,
            base_url=(payload.base_url or defaults["base_url"]).strip(),
            owner=owner,
            token=token,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_public(record)


def update_git_connection(connection_id: int, payload: GitConnectionUpdate) -> GitConnectionPublic:
    platform = payload.platform if payload.platform in GIT_PLATFORMS else "azure_devops"
    defaults = PLATFORM_DEFAULTS[platform]
    with db_session() as session:
        record = session.get(GitConnectionRecord, connection_id)
        if record is None:
            raise LookupError("Git platform not found.")
        owner = payload.owner.strip()
        if not owner:
            raise ValueError("Organization or owner is required.")
        record.label = payload.label.strip()
        record.platform = platform
        record.base_url = (payload.base_url or defaults["base_url"]).strip()
        record.owner = owner
        if payload.token and payload.token != SECRET_PLACEHOLDER:
            token = payload.token.strip()
            if not token:
                raise ValueError("Access token is required.")
            record.token = token
        elif not record.token.strip():
            raise ValueError("Access token is required.")
        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_public(record)


def delete_git_connection(connection_id: int) -> None:
    with db_session() as session:
        record = session.get(GitConnectionRecord, connection_id)
        if record is None:
            raise LookupError("Git platform not found.")
        project_count = (
            session.query(GitProjectRecord)
            .filter(GitProjectRecord.git_connection_id == connection_id)
            .count()
        )
        if project_count:
            raise ValueError("Remove projects using this git platform before deleting it.")
        session.delete(record)
        session.commit()

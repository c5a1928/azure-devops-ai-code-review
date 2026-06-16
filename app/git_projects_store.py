from __future__ import annotations

from app.db import db_session
from app.models import AppSettingsRecord, GitConnectionRecord, GitProjectRecord
from app.schemas import GitProjectCreate, GitProjectPublic, GitProjectUpdate
from app.services.git.types import GIT_PLATFORMS


def format_display_path(*, platform: str, owner: str, project: str, repo: str) -> str:
    if platform == "azure_devops":
        return " / ".join(part for part in (owner, project, repo) if part)
    if platform == "gitlab":
        return "/".join(part for part in (owner, project, repo) if part)
    return f"{owner} / {repo}" if owner else repo


def _to_public(record: GitProjectRecord, connection: GitConnectionRecord) -> GitProjectPublic:
    platform = connection.platform if connection.platform in GIT_PLATFORMS else "azure_devops"
    display_path = format_display_path(
        platform=platform,
        owner=connection.owner,
        project=record.project,
        repo=record.repo,
    )
    connection_label = connection.label.strip() or connection.owner.strip()
    return GitProjectPublic(
        id=record.id,
        git_connection_id=connection.id,
        git_connection_label=connection_label,
        platform=platform,
        label=record.label,
        project=record.project,
        repo=record.repo,
        display_path=display_path,
    )


def _get_connection(session, connection_id: int) -> GitConnectionRecord:
    connection = session.get(GitConnectionRecord, connection_id)
    if connection is None:
        raise ValueError("Git platform not found.")
    return connection


def _validate_project_fields(*, platform: str, project: str, repo: str) -> None:
    if not repo.strip():
        raise ValueError("Repository is required.")
    if platform == "azure_devops" and not project.strip():
        raise ValueError("Project is required for Azure DevOps.")


def migrate_legacy_git_projects() -> None:
    with db_session() as session:
        default_connection = session.query(GitConnectionRecord).order_by(GitConnectionRecord.id).first()
        if default_connection is None:
            return

        for project in session.query(GitProjectRecord).all():
            if project.git_connection_id is None:
                project.git_connection_id = default_connection.id
                session.add(project)

        if session.query(GitProjectRecord).count() > 0:
            session.commit()
            return

        record = session.get(AppSettingsRecord, 1)
        if record is None or not record.git_default_repo.strip():
            session.commit()
            return

        session.add(
            GitProjectRecord(
                git_connection_id=default_connection.id,
                label="",
                project=record.git_default_project.strip(),
                repo=record.git_default_repo.strip(),
            )
        )
        session.commit()


def list_git_projects() -> list[GitProjectPublic]:
    with db_session() as session:
        records = (
            session.query(GitProjectRecord, GitConnectionRecord)
            .join(GitConnectionRecord, GitProjectRecord.git_connection_id == GitConnectionRecord.id)
            .order_by(GitProjectRecord.id)
            .all()
        )
        return [_to_public(project, connection) for project, connection in records]


def count_git_projects() -> int:
    with db_session() as session:
        return session.query(GitProjectRecord).count()


def get_git_project(project_id: int) -> GitProjectPublic | None:
    with db_session() as session:
        row = (
            session.query(GitProjectRecord, GitConnectionRecord)
            .join(GitConnectionRecord, GitProjectRecord.git_connection_id == GitConnectionRecord.id)
            .filter(GitProjectRecord.id == project_id)
            .first()
        )
        if row is None:
            return None
        project, connection = row
        return _to_public(project, connection)


def create_git_project(payload: GitProjectCreate) -> GitProjectPublic:
    with db_session() as session:
        connection = _get_connection(session, payload.git_connection_id)
        platform = connection.platform if connection.platform in GIT_PLATFORMS else "azure_devops"
        project = payload.project.strip()
        repo = payload.repo.strip()
        _validate_project_fields(platform=platform, project=project, repo=repo)
        record = GitProjectRecord(
            git_connection_id=connection.id,
            label=payload.label.strip(),
            project=project,
            repo=repo,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_public(record, connection)


def update_git_project(project_id: int, payload: GitProjectUpdate) -> GitProjectPublic:
    with db_session() as session:
        record = session.get(GitProjectRecord, project_id)
        if record is None:
            raise LookupError("Project not found.")
        connection = _get_connection(session, payload.git_connection_id)
        platform = connection.platform if connection.platform in GIT_PLATFORMS else "azure_devops"
        project = payload.project.strip()
        repo = payload.repo.strip()
        _validate_project_fields(platform=platform, project=project, repo=repo)
        record.git_connection_id = connection.id
        record.label = payload.label.strip()
        record.project = project
        record.repo = repo
        session.add(record)
        session.commit()
        session.refresh(record)
        return _to_public(record, connection)


def delete_git_project(project_id: int) -> None:
    with db_session() as session:
        record = session.get(GitProjectRecord, project_id)
        if record is None:
            raise LookupError("Project not found.")
        session.delete(record)
        session.commit()

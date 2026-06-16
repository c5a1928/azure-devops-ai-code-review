from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GitConnectionRecord(Base):
    __tablename__ = "git_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(255), default="")
    platform: Mapped[str] = mapped_column(String(32), default="azure_devops")
    base_url: Mapped[str] = mapped_column(String(512), default="https://dev.azure.com")
    owner: Mapped[str] = mapped_column(String(255), default="")
    token: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class GitProjectRecord(Base):
    __tablename__ = "git_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    git_connection_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("git_connections.id"), nullable=True
    )
    label: Mapped[str] = mapped_column(String(255), default="")
    project: Mapped[str] = mapped_column(String(255), default="")
    repo: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class ReviewJobRecord(Base):
    __tablename__ = "review_jobs"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    git_project_id: Mapped[int] = mapped_column(Integer, default=0)
    display_path: Mapped[str] = mapped_column(String(512), default="")
    platform: Mapped[str] = mapped_column(String(32), default="")
    repo_name: Mapped[str] = mapped_column(String(255), default="")
    pr_id: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    step: Mapped[str] = mapped_column(String(64), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    pr_url: Mapped[str] = mapped_column(String(1024), default="")
    title: Mapped[str] = mapped_column(String(512), default="")
    verdict: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSettingsRecord(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    git_platform: Mapped[str] = mapped_column(String(32), default="azure_devops")
    git_base_url: Mapped[str] = mapped_column(String(512), default="https://dev.azure.com")
    git_owner: Mapped[str] = mapped_column(String(255), default="")
    git_default_project: Mapped[str] = mapped_column(String(255), default="")
    git_default_repo: Mapped[str] = mapped_column(String(255), default="")
    git_token: Mapped[str] = mapped_column(Text, default="")

    # Legacy columns kept for migration from older installs.
    azure_devops_base_url: Mapped[str] = mapped_column(String(512), default="https://dev.azure.com")
    azure_devops_org: Mapped[str] = mapped_column(String(255), default="")
    azure_devops_project: Mapped[str] = mapped_column(String(255), default="")
    azure_devops_pat: Mapped[str] = mapped_column(Text, default="")

    llm_provider: Mapped[str] = mapped_column(String(32), default="openai")
    openai_api_key: Mapped[str] = mapped_column(Text, default="")
    openai_base_url: Mapped[str] = mapped_column(String(512), default="https://api.openai.com/v1")
    openai_model: Mapped[str] = mapped_column(String(128), default="gpt-5.5")
    openai_temperature: Mapped[str] = mapped_column(String(32), default="0.0")
    openai_max_tokens: Mapped[str] = mapped_column(String(32), default="16384")
    openai_reasoning_effort: Mapped[str] = mapped_column(String(32), default="high")
    gmail_user: Mapped[str] = mapped_column(String(255), default="")
    gmail_app_password: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

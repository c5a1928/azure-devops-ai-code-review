from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.git.types import FileDiff, PullRequestContext, ReviewThread


class GitPlatformClient(ABC):
    platform: str

    @abstractmethod
    def get_authenticated_user(self) -> tuple[str, str]:
        """Return (user_id, email)."""

    @abstractmethod
    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        ...

    @abstractmethod
    def get_file_diffs(self, repo_name: str, pr: PullRequestContext, project: str | None = None) -> list[FileDiff]:
        ...

    @abstractmethod
    def list_active_reviewer_threads(
        self,
        repo_name: str,
        pr_id: int,
        reviewer_user_id: str,
        project: str | None = None,
    ) -> list[ReviewThread]:
        ...

    @abstractmethod
    def resolve_thread(
        self,
        repo_name: str,
        pr_id: int,
        thread_id: int,
        project: str | None = None,
    ) -> None:
        ...

    @abstractmethod
    def post_summary_comment(
        self,
        repo_name: str,
        pr_id: int,
        content: str,
        project: str | None = None,
    ) -> int:
        ...

    @abstractmethod
    def post_inline_comment(
        self,
        repo_name: str,
        pr_id: int,
        *,
        file_path: str,
        line: int,
        content: str,
        change_tracking_id: int,
        iteration_id: int,
        offset_start: int | None,
        offset_end: int | None,
        project: str | None = None,
    ) -> int:
        ...

    def build_pr_url(self, repo_name: str, pr_id: int, project: str | None = None) -> str:
        pr = self.get_pull_request(repo_name, pr_id, project=project)
        return pr.web_url

from __future__ import annotations

from app.runtime_settings import GitConnectionRuntime, ReviewRuntimeSettings
from app.services.azure_devops import AzureDevOpsClient
from app.services.git.base import GitPlatformClient
from app.services.git.bitbucket import BitbucketClient
from app.services.git.github import GitHubClient
from app.services.git.gitlab import GitLabClient
from app.services.git.types import GIT_PLATFORMS


class AzureDevOpsPlatformClient(GitPlatformClient):
    platform = "azure_devops"

    def __init__(self, client: AzureDevOpsClient) -> None:
        self._client = client

    def get_authenticated_user(self) -> tuple[str, str]:
        return self._client.get_authenticated_user()

    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> object:
        return self._client.get_pull_request(repo_name, pr_id)

    def get_file_diffs(self, repo_name: str, pr: object, project: str | None = None) -> list:
        return self._client.get_file_diffs(repo_name, pr)

    def list_active_reviewer_threads(
        self, repo_name: str, pr_id: int, reviewer_user_id: str, project: str | None = None
    ) -> list:
        return self._client.list_active_reviewer_threads(repo_name, pr_id, reviewer_user_id)

    def resolve_thread(self, repo_name: str, pr_id: int, thread_id: int, project: str | None = None) -> None:
        self._client.resolve_thread(repo_name, pr_id, thread_id)

    def post_summary_comment(self, repo_name: str, pr_id: int, content: str, project: str | None = None) -> int:
        return self._client.post_summary_comment(repo_name, pr_id, content)

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
        return self._client.post_inline_comment(
            repo_name,
            pr_id,
            file_path=file_path,
            line=line,
            content=content,
            change_tracking_id=change_tracking_id,
            iteration_id=iteration_id,
            offset_start=offset_start,
            offset_end=offset_end,
        )


def create_git_client(
    settings: ReviewRuntimeSettings,
    *,
    project: str | None = None,
    connection: GitConnectionRuntime | None = None,
) -> GitPlatformClient:
    active = connection or GitConnectionRuntime(
        id=0,
        label="",
        git_platform=settings.git_platform,
        git_base_url=settings.git_base_url,
        git_owner=settings.git_owner,
        git_token=settings.git_token,
    )
    platform = active.git_platform
    if platform not in GIT_PLATFORMS:
        raise ValueError(f"Unsupported git platform: {platform}")

    if platform == "azure_devops":
        ado_project = (project or ("" if connection else settings.git_default_project)).strip()
        return AzureDevOpsPlatformClient(
            AzureDevOpsClient(
                base_url=active.git_base_url,
                org=active.git_owner,
                project=ado_project,
                pat=active.git_token,
            )
        )
    if platform == "github":
        return GitHubClient(
            base_url=active.git_base_url,
            owner=active.git_owner,
            token=active.git_token,
        )
    if platform == "gitlab":
        return GitLabClient(
            base_url=active.git_base_url,
            namespace=active.git_owner,
            token=active.git_token,
        )
    if platform == "bitbucket":
        return BitbucketClient(
            base_url=active.git_base_url,
            workspace=active.git_owner,
            token=active.git_token,
        )
    raise ValueError(f"Unsupported git platform: {platform}")

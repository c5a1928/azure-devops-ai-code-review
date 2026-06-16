from __future__ import annotations

import logging
import urllib.parse

from app.services.git.base import GitPlatformClient
from app.services.git.http import request_json
from app.services.git.types import FileDiff, PullRequestContext, ReviewThread
from app.services.line_mapping import parse_new_file_changed_lines

logger = logging.getLogger(__name__)


class GitLabClient(GitPlatformClient):
    platform = "gitlab"

    def __init__(self, *, base_url: str, namespace: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace.strip()
        self.token = token.strip()

    def _project_path(self, repo_name: str, project: str | None = None) -> str:
        if project and "/" in project:
            return project.strip()
        parts = [part.strip() for part in (self.namespace, project, repo_name) if part and str(part).strip()]
        if parts:
            return "/".join(parts)
        return repo_name.strip()

    def _encoded_project(self, project_path: str) -> str:
        return urllib.parse.quote(project_path, safe="")

    def get_authenticated_user(self) -> tuple[str, str]:
        data = request_json(
            method="GET",
            url=f"{self.base_url}/user",
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )
        user_id = str(data.get("id", ""))
        email = data.get("email") or data.get("username") or ""
        if not email:
            email = f"{data.get('username', 'gitlab-user')}@users.noreply.gitlab.com"
        return user_id, email

    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        project_path = self._project_path(repo_name, project)
        encoded = self._encoded_project(project_path)
        data = request_json(
            method="GET",
            url=f"{self.base_url}/projects/{encoded}/merge_requests/{pr_id}",
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )
        return PullRequestContext(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("description") or "",
            source_commit=data["sha"],
            target_commit=data["diff_refs"]["base_sha"],
            repository_id=str(data.get("project_id", project_path)),
            web_url=data.get("web_url", ""),
            work_items=[],
        )

    def get_file_diffs(self, repo_name: str, pr: PullRequestContext, project: str | None = None) -> list[FileDiff]:
        project_path = self._project_path(repo_name, project)
        encoded = self._encoded_project(project_path)
        data = request_json(
            method="GET",
            url=f"{self.base_url}/projects/{encoded}/merge_requests/{pr.pr_id}/changes",
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )
        file_diffs: list[FileDiff] = []
        for index, change in enumerate(data.get("changes", []), start=1):
            path = change.get("new_path") or change.get("old_path") or ""
            diff_text = change.get("diff") or ""
            if not path or not diff_text:
                continue
            file_diffs.append(
                FileDiff(
                    path=f"/{path.lstrip('/')}",
                    change_tracking_id=index,
                    diff=diff_text,
                    new_content=_content_from_patch(diff_text),
                    iteration_id=1,
                    changed_lines=parse_new_file_changed_lines(diff_text),
                )
            )
        return file_diffs

    def list_active_reviewer_threads(
        self, repo_name: str, pr_id: int, reviewer_user_id: str, project: str | None = None
    ) -> list[ReviewThread]:
        return []

    def resolve_thread(
        self, repo_name: str, pr_id: int, thread_id: int, project: str | None = None
    ) -> None:
        return None

    def post_summary_comment(self, repo_name: str, pr_id: int, content: str, project: str | None = None) -> int:
        project_path = self._project_path(repo_name, project)
        encoded = self._encoded_project(project_path)
        data = request_json(
            method="POST",
            url=f"{self.base_url}/projects/{encoded}/merge_requests/{pr_id}/notes",
            token=self.token,
            auth_header="PRIVATE-TOKEN",
            body={"body": content},
        )
        return int(data.get("id", 0))

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
        project_path = self._project_path(repo_name, project)
        encoded = self._encoded_project(project_path)
        pr = self.get_pull_request(repo_name, pr_id, project=project)
        data = request_json(
            method="POST",
            url=f"{self.base_url}/projects/{encoded}/merge_requests/{pr_id}/discussions",
            token=self.token,
            auth_header="PRIVATE-TOKEN",
            body={
                "body": content,
                "position": {
                    "base_sha": pr.target_commit,
                    "start_sha": pr.target_commit,
                    "head_sha": pr.source_commit,
                    "position_type": "text",
                    "new_path": file_path.lstrip("/"),
                    "old_path": file_path.lstrip("/"),
                    "new_line": line,
                },
            },
        )
        notes = data.get("notes") or []
        if notes:
            return int(notes[0].get("id", 0))
        return int(data.get("id", 0))


def _content_from_patch(patch: str) -> str:
    lines: list[str] = []
    for line in patch.splitlines():
        if line.startswith("@@"):
            continue
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
        elif line.startswith(" "):
            lines.append(line[1:])
    return "\n".join(lines)

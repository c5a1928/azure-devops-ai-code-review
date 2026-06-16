from __future__ import annotations

import logging

from app.services.git.base import GitPlatformClient
from app.services.git.http import request_json
from app.services.git.types import FileDiff, PullRequestContext, ReviewThread
from app.services.line_mapping import parse_new_file_changed_lines

logger = logging.getLogger(__name__)


class BitbucketClient(GitPlatformClient):
    platform = "bitbucket"

    def __init__(self, *, base_url: str, workspace: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace = workspace.strip()
        self.token = token.strip()

    def _repo_slug(self, repo_name: str) -> str:
        return repo_name.strip()

    def get_authenticated_user(self) -> tuple[str, str]:
        data = request_json(method="GET", url=f"{self.base_url}/user", token=self.token)
        user_id = data.get("uuid") or data.get("account_id") or ""
        email = ""
        if isinstance(data.get("email"), str):
            email = data["email"]
        if not email:
            email = f"{data.get('username', 'bitbucket-user')}@users.noreply.bitbucket.org"
        return str(user_id), email

    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        repo = self._repo_slug(repo_name)
        data = request_json(
            method="GET",
            url=f"{self.base_url}/repositories/{self.workspace}/{repo}/pullrequests/{pr_id}",
            token=self.token,
        )
        source = data.get("source", {})
        destination = data.get("destination", {})
        return PullRequestContext(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("description") or "",
            source_commit=source.get("commit", {}).get("hash", ""),
            target_commit=destination.get("commit", {}).get("hash", ""),
            repository_id=repo,
            web_url=(data.get("links", {}).get("html", {}) or {}).get("href", ""),
            work_items=[],
        )

    def get_file_diffs(self, repo_name: str, pr: PullRequestContext, project: str | None = None) -> list[FileDiff]:
        repo = self._repo_slug(repo_name)
        data = request_json(
            method="GET",
            url=f"{self.base_url}/repositories/{self.workspace}/{repo}/pullrequests/{pr.pr_id}/diff",
            token=self.token,
        )
        file_diffs: list[FileDiff] = []
        for index, item in enumerate(data.get("values", []), start=1):
            path = ""
            diff_lines: list[str] = []
            for line in item.get("lines", []):
                path = path or line.get("filename", "")
                text = line.get("line", "")
                if text:
                    diff_lines.append(text)
            diff_text = "\n".join(diff_lines)
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
        repo = self._repo_slug(repo_name)
        data = request_json(
            method="POST",
            url=f"{self.base_url}/repositories/{self.workspace}/{repo}/pullrequests/{pr_id}/comments",
            token=self.token,
            body={"content": {"raw": content}},
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
        repo = self._repo_slug(repo_name)
        data = request_json(
            method="POST",
            url=f"{self.base_url}/repositories/{self.workspace}/{repo}/pullrequests/{pr_id}/comments",
            token=self.token,
            body={
                "content": {"raw": content},
                "inline": {
                    "path": file_path.lstrip("/"),
                    "to": line,
                },
            },
        )
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

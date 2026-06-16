from __future__ import annotations

import base64
import logging
import urllib.parse

from app.services.git.base import GitPlatformClient
from app.services.git.http import request_json
from app.services.git.types import FileDiff, PullRequestContext, ReviewThread
from app.services.line_mapping import parse_new_file_changed_lines

logger = logging.getLogger(__name__)


class GitHubClient(GitPlatformClient):
    platform = "github"

    def __init__(self, *, base_url: str, owner: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.owner = owner.strip()
        self.token = token.strip()
        self._head_sha: str | None = None

    def _api(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def get_authenticated_user(self) -> tuple[str, str]:
        data = request_json(method="GET", url=self._api("/user"), token=self.token)
        user_id = str(data.get("id", ""))
        email = data.get("email") or data.get("login") or ""
        if not email:
            email = f"{data.get('login', 'github-user')}@users.noreply.github.com"
        return user_id, email

    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        repo = repo_name.strip()
        data = request_json(
            method="GET",
            url=self._api(f"/repos/{self.owner}/{repo}/pulls/{pr_id}"),
            token=self.token,
        )
        self._head_sha = data["head"]["sha"]
        return PullRequestContext(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("body") or "",
            source_commit=data["head"]["sha"],
            target_commit=data["base"]["sha"],
            repository_id=str(data.get("node_id", repo)),
            web_url=data.get("html_url", ""),
            work_items=[],
        )

    def get_file_diffs(self, repo_name: str, pr: PullRequestContext, project: str | None = None) -> list[FileDiff]:
        repo = repo_name.strip()
        files = request_json(
            method="GET",
            url=self._api(f"/repos/{self.owner}/{repo}/pulls/{pr.pr_id}/files"),
            token=self.token,
        )
        file_diffs: list[FileDiff] = []
        for index, item in enumerate(files, start=1):
            path = item.get("filename", "")
            patch = item.get("patch") or ""
            if not path or not patch:
                continue
            status = item.get("status", "modified")
            new_content = ""
            if status != "removed":
                try:
                    new_content = self._fetch_file(repo, path, pr.source_commit)
                except Exception as exc:
                    logger.warning("Could not fetch %s at %s: %s", path, pr.source_commit, exc)
                    new_content = _content_from_patch(patch)
            file_diffs.append(
                FileDiff(
                    path=f"/{path.lstrip('/')}",
                    change_tracking_id=index,
                    diff=patch,
                    new_content=new_content,
                    iteration_id=1,
                    changed_lines=parse_new_file_changed_lines(patch),
                )
            )
        return file_diffs

    def _fetch_file(self, repo: str, path: str, ref: str) -> str:
        encoded_path = urllib.parse.quote(path.lstrip("/"), safe="/")
        data = request_json(
            method="GET",
            url=self._api(f"/repos/{self.owner}/{repo}/contents/{encoded_path}?ref={ref}"),
            token=self.token,
        )
        content = data.get("content", "")
        if data.get("encoding") == "base64":
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content

    def list_active_reviewer_threads(
        self, repo_name: str, pr_id: int, reviewer_user_id: str, project: str | None = None
    ) -> list[ReviewThread]:
        return []

    def resolve_thread(
        self, repo_name: str, pr_id: int, thread_id: int, project: str | None = None
    ) -> None:
        return None

    def post_summary_comment(self, repo_name: str, pr_id: int, content: str, project: str | None = None) -> int:
        repo = repo_name.strip()
        data = request_json(
            method="POST",
            url=self._api(f"/repos/{self.owner}/{repo}/pulls/{pr_id}/reviews"),
            token=self.token,
            body={"body": content, "event": "COMMENT"},
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
        repo = repo_name.strip()
        pr = self.get_pull_request(repo, pr_id, project=project)
        data = request_json(
            method="POST",
            url=self._api(f"/repos/{self.owner}/{repo}/pulls/{pr_id}/comments"),
            token=self.token,
            body={
                "body": content,
                "commit_id": pr.source_commit,
                "path": file_path.lstrip("/"),
                "line": line,
                "side": "RIGHT",
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

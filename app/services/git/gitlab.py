from __future__ import annotations

import logging
import re
import urllib.parse
from dataclasses import dataclass

from app.services.git.base import GitPlatformClient
from app.services.git.http import GitAPIError, request_json, request_text
from app.services.git.types import FileDiff, PullRequestContext, ReviewThread, WorkItemContext
from app.services.line_mapping import (
    GitlabDiffLine,
    build_gitlab_diff_position,
    parse_gitlab_diff_lines,
    parse_new_file_changed_lines,
    resolve_gitlab_diff_line,
)

logger = logging.getLogger(__name__)


@dataclass
class _MrChangeMeta:
    new_path: str
    old_path: str
    deleted_file: bool
    new_file: bool
    renamed_file: bool
    lines_by_new: dict[int, GitlabDiffLine]
    lines_by_old: dict[int, GitlabDiffLine]


class GitLabClient(GitPlatformClient):
    platform = "gitlab"

    def __init__(self, *, base_url: str, namespace: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.namespace = namespace.strip()
        self.token = token.strip()
        self._pr_cache: dict[tuple[str, int], PullRequestContext] = {}
        self._change_meta: dict[tuple[str, int, str], _MrChangeMeta] = {}

    def _project_path(self, repo_name: str, project: str | None = None) -> str:
        if project and "/" in project:
            return project.strip()
        parts = [part.strip() for part in (self.namespace, project, repo_name) if part and str(part).strip()]
        if parts:
            return "/".join(parts)
        return repo_name.strip()

    def _encoded_project(self, project_path: str) -> str:
        return urllib.parse.quote(project_path, safe="")

    def _mr_url(self, project_path: str, pr_id: int, suffix: str = "") -> str:
        encoded = self._encoded_project(project_path)
        return f"{self.base_url}/projects/{encoded}/merge_requests/{pr_id}{suffix}"

    def _paginate(self, url: str) -> list[dict]:
        items: list[dict] = []
        page = 1
        while True:
            separator = "&" if "?" in url else "?"
            page_url = f"{url}{separator}per_page=100&page={page}"
            batch = request_json(
                method="GET",
                url=page_url,
                token=self.token,
                auth_header="PRIVATE-TOKEN",
            )
            if not isinstance(batch, list):
                break
            if not batch:
                break
            items.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return items

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

    def _cache_key(self, repo_name: str, pr_id: int, project: str | None) -> tuple[str, int]:
        return (self._project_path(repo_name, project), pr_id)

    def _get_cached_pr(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        key = self._cache_key(repo_name, pr_id, project)
        if key not in self._pr_cache:
            self._pr_cache[key] = self.get_pull_request(repo_name, pr_id, project=project)
        return self._pr_cache[key]

    def get_pull_request(self, repo_name: str, pr_id: int, project: str | None = None) -> PullRequestContext:
        project_path = self._project_path(repo_name, project)
        data = request_json(
            method="GET",
            url=self._mr_url(project_path, pr_id),
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )
        diff_refs = data.get("diff_refs") or {}
        source_commit = diff_refs.get("head_sha") or data.get("sha") or ""
        target_commit = diff_refs.get("base_sha") or ""
        start_commit = diff_refs.get("start_sha") or target_commit
        work_items = self._get_linked_issues(project_path, pr_id)
        pr = PullRequestContext(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("description") or "",
            source_commit=source_commit,
            target_commit=target_commit,
            start_commit=start_commit,
            repository_id=str(data.get("project_id", project_path)),
            web_url=data.get("web_url", ""),
            work_items=work_items,
        )
        self._pr_cache[self._cache_key(repo_name, pr_id, project)] = pr
        return pr

    def _get_linked_issues(self, project_path: str, pr_id: int) -> list[WorkItemContext]:
        try:
            issues = request_json(
                method="GET",
                url=self._mr_url(project_path, pr_id, "/closes_issues"),
                token=self.token,
                auth_header="PRIVATE-TOKEN",
            )
        except GitAPIError as exc:
            logger.warning("Could not fetch linked issues for MR %s: %s", pr_id, exc)
            return []

        if not isinstance(issues, list):
            return []

        work_items: list[WorkItemContext] = []
        for issue in issues:
            try:
                work_items.append(
                    WorkItemContext(
                        id=int(issue.get("iid", issue.get("id", 0))),
                        title=str(issue.get("title", "")),
                        work_item_type="Issue",
                        state=str(issue.get("state", "")),
                        description=_normalize_issue_text(str(issue.get("description") or "")),
                        acceptance_criteria="",
                    )
                )
            except (TypeError, ValueError):
                continue
        return work_items

    def get_file_diffs(self, repo_name: str, pr: PullRequestContext, project: str | None = None) -> list[FileDiff]:
        project_path = self._project_path(repo_name, project)
        data = request_json(
            method="GET",
            url=self._mr_url(project_path, pr.pr_id, "/changes"),
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )
        file_diffs: list[FileDiff] = []
        cache_prefix = self._cache_key(repo_name, pr.pr_id, project)
        for index, change in enumerate(data.get("changes", []), start=1):
            new_path = (change.get("new_path") or "").strip()
            old_path = (change.get("old_path") or "").strip()
            path = new_path or old_path
            diff_text = change.get("diff") or ""
            if not path or not diff_text:
                continue

            deleted_file = bool(change.get("deleted_file"))
            new_file = bool(change.get("new_file"))
            renamed_file = bool(change.get("renamed_file"))
            normalized_path = f"/{path.lstrip('/')}"
            line_path = new_path or old_path
            lines_by_new, lines_by_old = parse_gitlab_diff_lines(diff_text, line_path)
            self._change_meta[(cache_prefix[0], cache_prefix[1], normalized_path.lstrip("/"))] = _MrChangeMeta(
                new_path=new_path or old_path,
                old_path=old_path or new_path,
                deleted_file=deleted_file,
                new_file=new_file,
                renamed_file=renamed_file,
                lines_by_new=lines_by_new,
                lines_by_old=lines_by_old,
            )

            new_content = ""
            if not deleted_file and pr.source_commit:
                try:
                    new_content = self._fetch_file(project_path, new_path or old_path, pr.source_commit)
                except Exception as exc:
                    logger.warning(
                        "Could not fetch %s at %s: %s",
                        new_path or old_path,
                        pr.source_commit,
                        exc,
                    )
                    new_content = _content_from_patch(diff_text)

            file_diffs.append(
                FileDiff(
                    path=normalized_path,
                    change_tracking_id=index,
                    diff=diff_text,
                    new_content=new_content,
                    iteration_id=1,
                    changed_lines=parse_new_file_changed_lines(diff_text),
                )
            )
        return file_diffs

    def _fetch_file(self, project_path: str, path: str, ref: str) -> str:
        encoded_project = self._encoded_project(project_path)
        encoded_path = urllib.parse.quote(path.lstrip("/"), safe="")
        return request_text(
            method="GET",
            url=(
                f"{self.base_url}/projects/{encoded_project}/repository/files/"
                f"{encoded_path}/raw?ref={urllib.parse.quote(ref, safe='')}"
            ),
            token=self.token,
            auth_header="PRIVATE-TOKEN",
        )

    def list_active_reviewer_threads(
        self, repo_name: str, pr_id: int, reviewer_user_id: str, project: str | None = None
    ) -> list[ReviewThread]:
        project_path = self._project_path(repo_name, project)
        discussions = self._paginate(self._mr_url(project_path, pr_id, "/discussions"))
        threads: list[ReviewThread] = []
        for discussion in discussions:
            discussion_id = discussion.get("id")
            if not discussion_id:
                continue

            notes = [note for note in discussion.get("notes", []) if not note.get("system")]
            if not notes:
                continue

            root_note = notes[0]
            author = root_note.get("author") or {}
            if str(author.get("id", "")) != str(reviewer_user_id):
                continue

            if root_note.get("resolved"):
                continue

            position = root_note.get("position") or {}
            file_path = position.get("new_path") or position.get("old_path")
            line = position.get("new_line") or position.get("old_line")
            if file_path:
                file_path = f"/{str(file_path).lstrip('/')}"

            threads.append(
                ReviewThread(
                    thread_id=str(discussion_id),
                    content=str(root_note.get("body") or ""),
                    file_path=file_path,
                    line=int(line) if line is not None else None,
                    status="active",
                )
            )
        return threads

    def resolve_thread(
        self, repo_name: str, pr_id: int, thread_id: int | str, project: str | None = None
    ) -> None:
        project_path = self._project_path(repo_name, project)
        encoded = self._encoded_project(project_path)
        request_json(
            method="PUT",
            url=(
                f"{self.base_url}/projects/{encoded}/merge_requests/{pr_id}/"
                f"discussions/{thread_id}"
            ),
            token=self.token,
            auth_header="PRIVATE-TOKEN",
            body={"resolved": True},
        )

    def post_summary_comment(self, repo_name: str, pr_id: int, content: str, project: str | None = None) -> int:
        project_path = self._project_path(repo_name, project)
        data = request_json(
            method="POST",
            url=self._mr_url(project_path, pr_id, "/notes"),
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
        pr = self._get_cached_pr(repo_name, pr_id, project=project)
        normalized_path = file_path.lstrip("/")
        cache_key = self._cache_key(repo_name, pr_id, project)
        change_meta = self._change_meta.get((cache_key[0], cache_key[1], normalized_path))

        new_path = change_meta.new_path if change_meta else normalized_path
        old_path = change_meta.old_path if change_meta else normalized_path
        deleted_file = change_meta.deleted_file if change_meta else False

        diff_line = None
        if change_meta:
            diff_line = resolve_gitlab_diff_line(
                change_meta.lines_by_new,
                change_meta.lines_by_old,
                requested_line=line,
                deleted_file=deleted_file,
            )

        if diff_line is None:
            logger.warning(
                "No GitLab diff line for %s:%s in MR %s; posting as MR note",
                file_path,
                line,
                pr_id,
            )
            return self.post_summary_comment(
                repo_name,
                pr_id,
                f"**{file_path.lstrip('/')}:{line}**\n\n{content}",
                project=project,
            )

        position = build_gitlab_diff_position(
            base_sha=pr.target_commit,
            start_sha=pr.start_commit or pr.target_commit,
            head_sha=pr.source_commit,
            old_path=old_path,
            new_path=new_path,
            diff_line=diff_line,
        )

        try:
            data = request_json(
                method="POST",
                url=self._mr_url(project_path, pr_id, "/discussions"),
                token=self.token,
                auth_header="PRIVATE-TOKEN",
                body={"body": content, "position": position},
            )
        except GitAPIError as exc:
            if exc.status_code != 400:
                raise
            logger.warning(
                "GitLab rejected inline position for %s:%s in MR %s (%s); posting as MR note",
                file_path,
                line,
                pr_id,
                exc,
            )
            return self.post_summary_comment(
                repo_name,
                pr_id,
                f"**{file_path.lstrip('/')}:{line}**\n\n{content}",
                project=project,
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


def _normalize_issue_text(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<(br|/p|/div|/li)\s*/?>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()

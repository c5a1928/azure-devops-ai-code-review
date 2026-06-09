from __future__ import annotations

import base64
import difflib
import html
import json
import logging
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError

from app.services.line_mapping import parse_new_file_changed_lines

logger = logging.getLogger(__name__)


@dataclass
class FileDiff:
    path: str
    change_tracking_id: int
    diff: str
    new_content: str
    iteration_id: int = 1
    changed_lines: set[int] = field(default_factory=set)


@dataclass
class ReviewThread:
    thread_id: int
    content: str
    file_path: str | None
    line: int | None
    status: str


@dataclass
class WorkItemContext:
    id: int
    title: str
    work_item_type: str
    state: str
    description: str
    acceptance_criteria: str


@dataclass
class PullRequestContext:
    pr_id: int
    title: str
    description: str
    source_commit: str
    target_commit: str
    repository_id: str
    web_url: str
    work_items: list[WorkItemContext] = field(default_factory=list)


class AzureDevOpsAPIError(RuntimeError):
    def __init__(self, status_code: int, url: str, message: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"Azure DevOps API error {status_code} for {url}: {message}")


class AzureDevOpsClient:
    def __init__(
        self,
        *,
        base_url: str,
        org: str,
        project: str,
        pat: str,
        request_timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.org = org
        self.project = project
        self.pat = pat
        self.request_timeout = request_timeout
        self._auth = base64.b64encode(f":{pat}".encode()).decode()
        self._project_encoded = urllib.parse.quote(project)

    def _urlopen(self, req: urllib.request.Request) -> dict:
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                return json.load(resp)
        except HTTPError as exc:
            body = exc.read().decode(errors="replace")[:1000]
            raise AzureDevOpsAPIError(exc.code, req.full_url, body or exc.reason) from exc
        except URLError as exc:
            raise AzureDevOpsAPIError(0, req.full_url, str(exc.reason)) from exc

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}/{self.org}/{self._project_encoded}/_apis{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Basic {self._auth}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        return self._urlopen(req)

    def _org_request(self, method: str, path: str, body: dict | None = None) -> dict:
        url = f"{self.base_url}/{self.org}/_apis{path}"
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Basic {self._auth}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json")
        return self._urlopen(req)

    def get_authenticated_user(self) -> tuple[str, str]:
        data = self._org_request("GET", "/connectionData?api-version=7.1-preview")
        user = data.get("authenticatedUser", {})
        user_id = user.get("id", "")
        account = user.get("properties", {}).get("Account", {}).get("$value")
        email = account or user.get("uniqueName") or ""
        if not user_id or not email:
            raise ValueError("Could not resolve PAT owner identity from Azure DevOps")
        return user_id, email

    def get_authenticated_user_email(self) -> str:
        return self.get_authenticated_user()[1]

    def get_pull_request(self, repo_name: str, pr_id: int) -> PullRequestContext:
        data = self._request(
            "GET",
            f"/git/repositories/{repo_name}/pullRequests/{pr_id}?api-version=7.1",
        )
        work_items = self.get_linked_work_items(repo_name, pr_id)
        return PullRequestContext(
            pr_id=pr_id,
            title=data.get("title", ""),
            description=data.get("description", ""),
            source_commit=data["lastMergeSourceCommit"]["commitId"],
            target_commit=data["lastMergeTargetCommit"]["commitId"],
            repository_id=data["repository"]["id"],
            web_url=data.get("url", ""),
            work_items=work_items,
        )

    def get_linked_work_items(self, repo_name: str, pr_id: int) -> list[WorkItemContext]:
        try:
            linked = self._request(
                "GET",
                f"/git/repositories/{repo_name}/pullRequests/{pr_id}/workitems?api-version=7.1",
            )
        except AzureDevOpsAPIError as exc:
            logger.warning("Could not fetch linked work items for PR %s: %s", pr_id, exc)
            return []

        work_item_ids: list[int] = []
        for item in linked.get("value", []):
            try:
                work_item_ids.append(int(item["id"]))
            except (KeyError, TypeError, ValueError):
                continue

        if not work_item_ids:
            return []

        return self._get_work_items(work_item_ids)

    def _get_work_items(self, work_item_ids: list[int]) -> list[WorkItemContext]:
        work_items: list[WorkItemContext] = []

        chunk_size = 20
        for index in range(0, len(work_item_ids), chunk_size):
            chunk = work_item_ids[index : index + chunk_size]
            ids_param = ",".join(str(item_id) for item_id in chunk)
            data = self._fetch_work_items_chunk(ids_param)
            if data is None:
                continue

            for item in data.get("value", []):
                item_fields = item.get("fields", {})
                work_items.append(
                    WorkItemContext(
                        id=int(item_fields.get("System.Id", item.get("id", 0))),
                        title=str(item_fields.get("System.Title", "")),
                        work_item_type=str(item_fields.get("System.WorkItemType", "")),
                        state=str(item_fields.get("System.State", "")),
                        description=self._normalize_work_item_text(
                            str(item_fields.get("System.Description", ""))
                        ),
                        acceptance_criteria=self._normalize_work_item_text(
                            self._extract_acceptance_criteria(item_fields)
                        ),
                    )
                )

        return work_items

    def _fetch_work_items_chunk(self, ids_param: str) -> dict | None:
        try:
            # Omit `fields` so Azure DevOps returns all fields, including
            # "Acceptance Criteria" (Microsoft.VSTS.Common.AcceptanceCriteria).
            return self._request(
                "GET",
                f"/wit/workitems?ids={ids_param}&api-version=7.1",
            )
        except AzureDevOpsAPIError as exc:
            logger.warning(
                "Could not fetch work item details for %s: %s",
                ids_param,
                exc,
            )
            return None

    @staticmethod
    def _extract_acceptance_criteria(item_fields: dict) -> str:
        known_fields = [
            "Microsoft.VSTS.Common.AcceptanceCriteria",
        ]
        for field_name in known_fields:
            value = item_fields.get(field_name)
            if value:
                return str(value)

        for field_name, value in item_fields.items():
            normalized = field_name.lower().replace(".", "").replace("_", "")
            if "acceptancecriteria" in normalized and value:
                return str(value)

        return ""

    @staticmethod
    def _normalize_work_item_text(value: str) -> str:
        if not value:
            return ""
        text = html.unescape(value)
        text = re.sub(r"<(br|/p|/div|/li)\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    def get_file_diffs(self, repo_name: str, pr: PullRequestContext) -> list[FileDiff]:
        iterations = self._request(
            "GET",
            f"/git/repositories/{repo_name}/pullRequests/{pr.pr_id}/iterations?api-version=7.1",
        )
        if not iterations.get("value"):
            return []

        iteration_id = max(item["id"] for item in iterations["value"])
        changes = self._request(
            "GET",
            f"/git/repositories/{repo_name}/pullRequests/{pr.pr_id}/iterations/{iteration_id}/changes?api-version=7.1",
        )

        file_diffs: list[FileDiff] = []
        for entry in changes.get("changeEntries", []):
            item = entry.get("item", {})
            if item.get("isFolder"):
                continue

            path = item.get("path", "")
            if not path:
                continue

            change_type = str(entry.get("changeType", "edit")).lower()
            source_path = path
            target_path = path

            source_server_item = entry.get("sourceServerItem") or item.get("sourceServerItem")
            if isinstance(source_server_item, dict) and source_server_item.get("path"):
                target_path = source_server_item["path"]

            try:
                source_content, target_content = self._get_contents_for_change(
                    repo_name,
                    pr,
                    change_type=change_type,
                    source_path=source_path,
                    target_path=target_path,
                )
            except AzureDevOpsAPIError as exc:
                logger.warning("Skipping %s (%s): %s", path, change_type, exc)
                continue

            diff_text = self._build_diff_text(target_content, source_content, target_path, source_path)
            if not diff_text.strip():
                continue

            file_diffs.append(
                FileDiff(
                    path=source_path,
                    change_tracking_id=entry.get("changeTrackingId", 1),
                    diff=diff_text,
                    new_content=source_content,
                    iteration_id=iteration_id,
                    changed_lines=parse_new_file_changed_lines(diff_text),
                )
            )
        return file_diffs

    def _get_contents_for_change(
        self,
        repo_name: str,
        pr: PullRequestContext,
        *,
        change_type: str,
        source_path: str,
        target_path: str,
    ) -> tuple[str, str]:
        if change_type == "add":
            return self._get_file_content(repo_name, source_path, pr.source_commit), ""

        if change_type == "delete":
            return "", self._get_file_content(repo_name, target_path, pr.target_commit)

        source_content = self._get_file_content(repo_name, source_path, pr.source_commit)
        target_content = self._get_file_content(repo_name, target_path, pr.target_commit)
        return source_content, target_content

    def _build_diff_text(
        self,
        target_content: str,
        source_content: str,
        target_path: str,
        source_path: str,
    ) -> str:
        diff_lines = difflib.unified_diff(
            target_content.splitlines(),
            source_content.splitlines(),
            fromfile=target_path,
            tofile=source_path,
            lineterm="",
        )
        return "\n".join(diff_lines)

    def _get_file_content(self, repo_name: str, path: str, commit_id: str) -> str:
        encoded_path = urllib.parse.quote(path, safe="")
        try:
            data = self._request(
                "GET",
                f"/git/repositories/{repo_name}/items?path={encoded_path}"
                f"&versionDescriptor.version={commit_id}"
                f"&versionDescriptor.versionType=commit"
                f"&includeContent=true&api-version=7.1",
            )
        except AzureDevOpsAPIError as exc:
            if exc.status_code == 404:
                return ""
            raise

        if data.get("isBinary"):
            logger.info("Skipping binary file content for %s at %s", path, commit_id)
            return ""

        content = data.get("content")
        if content is not None:
            return content

        object_id = data.get("objectId")
        if object_id:
            return self._get_blob_text(repo_name, object_id)

        return ""

    def _get_blob_text(self, repo_name: str, object_id: str) -> str:
        try:
            data = self._request(
                "GET",
                f"/git/repositories/{repo_name}/blobs/{object_id}?api-version=7.1",
            )
        except AzureDevOpsAPIError as exc:
            if exc.status_code == 404:
                return ""
            raise

        content = data.get("content")
        if not content:
            return ""

        encoding = str(data.get("encoding", "")).lower()
        if encoding == "base64":
            try:
                return base64.b64decode(content).decode("utf-8")
            except UnicodeDecodeError:
                logger.info("Skipping non-UTF-8 blob %s", object_id)
                return ""

        return content

    @staticmethod
    def _is_active_thread_status(status: object) -> bool:
        if isinstance(status, int):
            return status == 1
        return str(status).lower() in {"active", "pending", "unknown"}

    def list_active_reviewer_threads(
        self,
        repo_name: str,
        pr_id: int,
        reviewer_user_id: str,
    ) -> list[ReviewThread]:
        data = self._request(
            "GET",
            f"/git/repositories/{repo_name}/pullRequests/{pr_id}/threads?api-version=7.1",
        )

        threads: list[ReviewThread] = []
        for thread in data.get("value", []):
            if thread.get("isDeleted"):
                continue

            if not self._is_active_thread_status(thread.get("status", "active")):
                continue
            status = str(thread.get("status", "active"))

            comments = [
                comment
                for comment in thread.get("comments", [])
                if not comment.get("isDeleted")
                and str(comment.get("commentType", "text")).lower() in {"text", "1"}
            ]
            if not comments:
                continue

            root_comment = next(
                (comment for comment in comments if comment.get("parentCommentId", 0) == 0),
                comments[0],
            )
            author = root_comment.get("author", {})
            if author.get("id") != reviewer_user_id:
                continue

            thread_context = thread.get("threadContext") or {}
            file_path = thread_context.get("filePath")
            line = None
            right_start = thread_context.get("rightFileStart") or {}
            if isinstance(right_start, dict):
                line = right_start.get("line")

            threads.append(
                ReviewThread(
                    thread_id=int(thread["id"]),
                    content=str(root_comment.get("content", "")).strip(),
                    file_path=file_path,
                    line=int(line) if line else None,
                    status=status,
                )
            )

        return threads

    def resolve_thread(self, repo_name: str, pr_id: int, thread_id: int) -> None:
        self._request(
            "PATCH",
            f"/git/repositories/{repo_name}/pullRequests/{pr_id}/threads/{thread_id}?api-version=7.1",
            {"status": "fixed"},
        )

    def post_summary_comment(self, repo_name: str, pr_id: int, content: str) -> int:
        body = {
            "comments": [
                {
                    "parentCommentId": 0,
                    "content": content,
                    "commentType": 1,
                }
            ],
            "status": 1,
        }
        resp = self._request(
            "POST",
            f"/git/repositories/{repo_name}/pullRequests/{pr_id}/threads?api-version=7.1",
            body,
        )
        return resp["id"]

    def post_inline_comment(
        self,
        repo_name: str,
        pr_id: int,
        *,
        file_path: str,
        line: int,
        content: str,
        change_tracking_id: int = 1,
        iteration_id: int = 1,
        offset_start: int = 1,
        offset_end: int = 1,
    ) -> int:
        body = {
            "comments": [
                {
                    "parentCommentId": 0,
                    "content": content,
                    "commentType": 1,
                }
            ],
            "status": 1,
            "threadContext": {
                "filePath": file_path,
                "leftFileStart": None,
                "leftFileEnd": None,
                "rightFileStart": {"line": line, "offset": offset_start},
                "rightFileEnd": {"line": line, "offset": max(offset_end, offset_start)},
            },
            "pullRequestThreadContext": {
                "changeTrackingId": change_tracking_id,
                "iterationContext": {
                    "firstComparingIteration": 1,
                    "secondComparingIteration": iteration_id,
                },
            },
        }
        resp = self._request(
            "POST",
            f"/git/repositories/{repo_name}/pullRequests/{pr_id}/threads?api-version=7.1",
            body,
        )
        return resp["id"]

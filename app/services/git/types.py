from __future__ import annotations

from dataclasses import dataclass, field


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
    thread_id: int | str
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
    start_commit: str = ""


GIT_PLATFORMS = frozenset({"azure_devops", "github", "gitlab", "bitbucket"})

PLATFORM_BASE_URL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "azure_devops": [
        {"label": "Azure DevOps Services (cloud)", "url": "https://dev.azure.com"},
        {
            "label": "Azure DevOps Server (on-premises)",
            "url": "https://your-server/tfs",
        },
    ],
    "github": [
        {"label": "GitHub.com", "url": "https://api.github.com"},
        {
            "label": "GitHub Enterprise Server",
            "url": "https://github.example.com/api/v3",
        },
    ],
    "gitlab": [
        {"label": "GitLab.com", "url": "https://gitlab.com/api/v4"},
        {
            "label": "GitLab self-managed",
            "url": "https://gitlab.example.com/api/v4",
        },
    ],
    "bitbucket": [
        {"label": "Bitbucket Cloud", "url": "https://api.bitbucket.org/2.0"},
        {
            "label": "Bitbucket Data Center",
            "url": "https://bitbucket.example.com/rest/api/1.0",
        },
    ],
}

PLATFORM_DEFAULTS: dict[str, dict[str, str]] = {
    "azure_devops": {
        "base_url": "https://dev.azure.com",
        "owner_label": "Organization",
        "project_label": "Project",
        "repo_label": "Repository",
        "token_label": "Personal access token",
    },
    "github": {
        "base_url": "https://api.github.com",
        "owner_label": "Organization or user",
        "project_label": "Project (unused)",
        "repo_label": "Repository",
        "token_label": "Personal access token",
    },
    "gitlab": {
        "base_url": "https://gitlab.com/api/v4",
        "owner_label": "Group or namespace",
        "project_label": "Subgroup (optional)",
        "repo_label": "Repository",
        "token_label": "Personal access token",
    },
    "bitbucket": {
        "base_url": "https://api.bitbucket.org/2.0",
        "owner_label": "Workspace",
        "project_label": "Project (unused)",
        "repo_label": "Repository slug",
        "token_label": "App password or access token",
    },
}

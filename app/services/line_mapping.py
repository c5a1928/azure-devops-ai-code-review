from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


def normalize_repo_path(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        return f"/{path}"
    return path


def parse_new_file_changed_lines(diff: str) -> set[int]:
    changed: set[int] = set()
    current_new_line = 0

    for line in diff.splitlines():
        if line.startswith("@@"):
            match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                current_new_line = int(match.group(1))
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            changed.add(current_new_line)
            current_new_line += 1
        elif line.startswith("-"):
            continue
        elif line.startswith(" "):
            current_new_line += 1

    return changed


def format_numbered_content(content: str, *, max_lines: int = 800) -> str:
    lines = content.splitlines()
    if len(lines) <= max_lines:
        return "\n".join(f"{index:5d}| {line}" for index, line in enumerate(lines, 1))

    half = max_lines // 2
    head = "\n".join(f"{index:5d}| {line}" for index, line in enumerate(lines[:half], 1))
    tail_start = len(lines) - half + 1
    tail = "\n".join(
        f"{index:5d}| {line}" for index, line in enumerate(lines[-half:], tail_start)
    )
    omitted = len(lines) - (half * 2)
    return f"{head}\n... ({omitted} lines omitted) ...\n{tail}"


def resolve_comment_position(
    *,
    new_content: str,
    changed_lines: set[int],
    requested_line: int,
    code_snippet: str | None,
) -> tuple[int, int, int]:
    """Return (line, offset_start, offset_end) for Azure DevOps thread context."""
    lines = new_content.splitlines()
    if not lines:
        return max(requested_line, 1), 1, 1

    snippet = (code_snippet or "").strip()
    if snippet:
        for index, line in enumerate(lines, 1):
            if snippet in line:
                return index, _offset_start(line, snippet), _offset_end(line, snippet)

        normalized_snippet = _normalize_code(snippet)
        for index, line in enumerate(lines, 1):
            if normalized_snippet in _normalize_code(line):
                return index, 1, max(len(line.strip()), 1)

    if 1 <= requested_line <= len(lines):
        line_text = lines[requested_line - 1]
        return requested_line, 1, max(len(line_text.strip()), 1)

    if changed_lines:
        nearest = min(changed_lines, key=lambda line: abs(line - requested_line))
        line_text = lines[nearest - 1] if 1 <= nearest <= len(lines) else ""
        return nearest, 1, max(len(line_text.strip()), 1)

    clamped = max(1, min(requested_line, len(lines)))
    line_text = lines[clamped - 1]
    return clamped, 1, max(len(line_text.strip()), 1)


def _offset_start(line: str, snippet: str) -> int:
    position = line.find(snippet)
    if position >= 0:
        return position + 1
    return 1


def _offset_end(line: str, snippet: str) -> int:
    position = line.find(snippet)
    if position >= 0:
        return position + len(snippet)
    return max(len(line.strip()), 1)


def _normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", value)


@dataclass(frozen=True)
class GitlabDiffLine:
    old_line: int
    new_line: int
    is_added: bool
    is_removed: bool
    line_code: str
    line_range_type: str


def gitlab_line_code(file_path: str, old_line: int, new_line: int) -> str:
    """GitLab diff line code: sha1(path)_old_line_new_line."""
    return f"{hashlib.sha1(file_path.encode()).hexdigest()}_{old_line}_{new_line}"


def parse_gitlab_diff_lines(
    diff: str, file_path: str
) -> tuple[dict[int, GitlabDiffLine], dict[int, GitlabDiffLine]]:
    """Map diff hunks to GitLab line positions keyed by new/old file line numbers."""
    by_new: dict[int, GitlabDiffLine] = {}
    by_old: dict[int, GitlabDiffLine] = {}
    old_line = 0
    new_line = 0

    for raw in diff.splitlines():
        if raw.startswith("@@"):
            match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", raw)
            if match:
                old_line = int(match.group(1))
                new_line = int(match.group(2))
            continue
        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            entry = GitlabDiffLine(
                old_line=0,
                new_line=new_line,
                is_added=True,
                is_removed=False,
                line_code=gitlab_line_code(file_path, 0, new_line),
                line_range_type="new",
            )
            by_new[new_line] = entry
            new_line += 1
        elif raw.startswith("-"):
            entry = GitlabDiffLine(
                old_line=old_line,
                new_line=0,
                is_added=False,
                is_removed=True,
                line_code=gitlab_line_code(file_path, old_line, 0),
                line_range_type="old",
            )
            by_old[old_line] = entry
            old_line += 1
        elif raw.startswith(" "):
            entry = GitlabDiffLine(
                old_line=old_line,
                new_line=new_line,
                is_added=False,
                is_removed=False,
                line_code=gitlab_line_code(file_path, old_line, new_line),
                line_range_type="old",
            )
            by_new[new_line] = entry
            by_old[old_line] = entry
            old_line += 1
            new_line += 1

    return by_new, by_old


def resolve_gitlab_diff_line(
    lines_by_new: dict[int, GitlabDiffLine],
    lines_by_old: dict[int, GitlabDiffLine],
    *,
    requested_line: int,
    deleted_file: bool,
) -> GitlabDiffLine | None:
    index = lines_by_old if deleted_file else lines_by_new
    if not index:
        return None
    if requested_line in index:
        return index[requested_line]

    preferred = {line: entry for line, entry in lines_by_new.items() if entry.is_added}
    pool = preferred or index
    nearest = min(pool.keys(), key=lambda line: abs(line - requested_line))
    return pool[nearest]


def build_gitlab_diff_position(
    *,
    base_sha: str,
    start_sha: str,
    head_sha: str,
    old_path: str,
    new_path: str,
    diff_line: GitlabDiffLine,
) -> dict[str, object]:
    position: dict[str, object] = {
        "base_sha": base_sha,
        "start_sha": start_sha,
        "head_sha": head_sha,
        "position_type": "text",
        "old_path": old_path,
        "new_path": new_path,
    }

    if diff_line.is_removed:
        position["old_line"] = diff_line.old_line
    elif diff_line.is_added:
        position["new_line"] = diff_line.new_line
    else:
        position["old_line"] = diff_line.old_line
        position["new_line"] = diff_line.new_line

    line_range_entry: dict[str, object] = {
        "line_code": diff_line.line_code,
        "type": diff_line.line_range_type,
    }
    if diff_line.is_removed:
        line_range_entry["old_line"] = diff_line.old_line
    elif diff_line.is_added:
        line_range_entry["new_line"] = diff_line.new_line
    else:
        line_range_entry["old_line"] = diff_line.old_line
        line_range_entry["new_line"] = diff_line.new_line

    position["line_range"] = {
        "start": dict(line_range_entry),
        "end": dict(line_range_entry),
    }
    return position

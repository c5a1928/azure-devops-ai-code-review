from __future__ import annotations

import re


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

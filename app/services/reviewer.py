from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from app.services.git.types import FileDiff, PullRequestContext
from app.services.framework_detection import build_framework_review_section
from app.services.openai_chat import call_chat_completion
from app.services.line_mapping import (
    format_numbered_content,
    normalize_repo_path,
    resolve_comment_position,
)

logger = logging.getLogger(__name__)

_SECTION_LABEL_PATTERN = re.compile(
    r"(?:\*\*)?(?:Problem|Why it matters|Specific fix)(?:\*\*)?\s*→\s*",
    re.IGNORECASE,
)


def _normalize_comment_content(content: str) -> str:
    normalized = _SECTION_LABEL_PATTERN.sub("", content.strip())
    return re.sub(r"\n{3,}", "\n\n", normalized).strip()


@dataclass
class InlineComment:
    file_path: str
    line: int
    content: str
    change_tracking_id: int = 1
    iteration_id: int = 1
    offset_start: int = 1
    offset_end: int = 1


@dataclass
class ReviewDiagnostics:
    llm_verdict: str
    llm_inline_count: int
    parsed_inline_count: int
    dropped_inline_count: int
    drop_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_llm_response: str = ""


@dataclass
class ReviewResult:
    summary: str
    inline_comments: list[InlineComment]
    verdict: str
    detected_frameworks: list[str]
    diagnostics: ReviewDiagnostics | None = None


class CodeReviewer:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort

    def review(self, pr: PullRequestContext, file_diffs: list[FileDiff]) -> ReviewResult:
        if not file_diffs:
            return ReviewResult(
                summary="",
                inline_comments=[],
                verdict="no_changes",
                detected_frameworks=[],
                diagnostics=ReviewDiagnostics(
                    llm_verdict="no_changes",
                    llm_inline_count=0,
                    parsed_inline_count=0,
                    dropped_inline_count=0,
                ),
            )

        detected_frameworks, framework_section = build_framework_review_section(file_diffs)
        prompt = self._build_prompt(pr, file_diffs, detected_frameworks, framework_section)
        raw = self._call_llm(prompt, detected_frameworks)
        logger.info("LLM review raw response:\n%s", raw)
        result = self._parse_response(raw, file_diffs)
        return ReviewResult(
            summary=result.summary,
            inline_comments=result.inline_comments,
            verdict=result.verdict,
            detected_frameworks=detected_frameworks,
            diagnostics=result.diagnostics,
        )

    def _has_python_files(self, file_diffs: list[FileDiff]) -> bool:
        return any(item.path.lower().endswith(".py") for item in file_diffs)

    def _format_work_items(self, pr: PullRequestContext) -> str:
        if not pr.work_items:
            return "No linked work items found on this pull request."

        blocks: list[str] = []
        for item in pr.work_items:
            blocks.append(
                "\n".join(
                    [
                        f"Work Item #{item.id} [{item.work_item_type}] — {item.title} ({item.state})",
                        f"Description:\n{item.description or '(none)'}",
                        f"Acceptance criteria:\n{item.acceptance_criteria or '(none)'}",
                    ]
                )
            )
        return "\n\n---\n\n".join(blocks)

    def _functional_review_guidelines(self) -> str:
        return """
Functional / logical review:
- Use linked work items and acceptance criteria as the source of truth.
- Flag unmet requirements, wrong control flow, bad state/data handling, and regressions in changed code.
- Reference work item IDs when flagging logic gaps (e.g. "WI #1234: …").
"""

    def _efficiency_review_guidelines(self) -> str:
        return """
Efficiency review:
- Flag N+1 queries/API calls, nested loops, redundant work, and unbounded memory use in changed code.
- Name the waste and suggest a concrete fix (e.g. "N+1 queries — batch load related rows").
"""

    def _python_review_guidelines(self) -> str:
        return """
Python 3 / PEP review (for `.py` changes):
- Enforce PEP 8 on changed lines and flag error-prone patterns (bare except, mutable defaults, Python 2 idioms).
- Cite the rule briefly (e.g. "PEP 8: E722 bare except"). Only review changed lines.
"""

    def _build_prompt(
        self,
        pr: PullRequestContext,
        file_diffs: list[FileDiff],
        detected_frameworks: list[str],
        framework_section: str,
    ) -> str:
        file_blocks = []
        for item in file_diffs:
            changed = ", ".join(str(line) for line in sorted(item.changed_lines)[:40])
            file_blocks.append(
                "\n".join(
                    [
                        f"### {item.path}",
                        f"Changed lines in new file: {changed or '(see diff)'}",
                        "Numbered new file:",
                        f"```\n{format_numbered_content(item.new_content)}\n```",
                        "Diff:",
                        f"```diff\n{item.diff}\n```",
                    ]
                )
            )

        python_section = ""
        if self._has_python_files(file_diffs):
            python_section = self._python_review_guidelines()

        detected_stack = ", ".join(detected_frameworks) if detected_frameworks else "none detected"

        work_items_section = self._format_work_items(pr)

        return f"""You are a senior engineer reviewing a pull request before merge. Evaluate whether the change correctly implements the required business logic — not just whether the syntax is valid.

Pull request title: {pr.title}
Description:
{pr.description or "(none)"}

Linked work items (expected behaviour and acceptance criteria):
{work_items_section}

Detected frameworks/libraries in this PR: {detected_stack}

Review the diffs and return ONLY valid JSON with this schema:
{{
  "summary": "Optional PR-level comment. Use only when a critical issue spans multiple files.",
  "verdict": "critical|no_critical_issues",
  "inline_comments": [
    {{
      "file_path": "/exact/path/from/diff",
      "line": 42,
      "code_snippet": "exact code from the numbered new file view",
      "content": "Concise review comment in markdown"
    }}
  ]
}}

Review policy — follow strictly:
- You are a strict reviewer, not a permissive one. If you find ANY actionable issue in the categories below, you MUST return at least one `inline_comment` and set `"verdict": "critical"`.
- Use `"verdict": "no_critical_issues"` ONLY when you have checked every category below and found zero actionable problems in changed code.
- Categories in scope (all are mandatory to check): functional/logical correctness, efficiency, Python 3/PEP (for .py files), and framework maintainability (when stacks are detected).
- Report: logic gaps vs work items, unmet acceptance criteria, bugs, security issues, data loss risk, broken runtime behaviour, merge-blocking regressions, meaningful efficiency problems, non-idiomatic framework usage, and meaningful PEP violations in changed code.
- Code that "works" but is wrong, fragile, inefficient, non-idiomatic for the detected stack, or violates PEP on changed lines MUST be flagged.
- Do not suppress findings because another category already has issues, or because the change is small.
- For non-Python files, ignore cosmetic style unless it hides a real defect.
- Do NOT give compliments, praise, or approval language.
- Do NOT mention automation, AI, bots, or that this is an automated review. Write as a human reviewer would.
- Return empty comments ONLY when all categories above have zero actionable issues in changed code.
{framework_section}
{self._functional_review_guidelines()}
{self._efficiency_review_guidelines()}
{python_section}
Inline comment format (every comment must be actionable):
- Write in plain prose paragraphs. Do NOT use section labels or prefixes such as "Problem →", "Why it matters →", or "Specific fix →".
- Flow naturally: state what is wrong (reference work items when relevant), show the offending code, explain the impact, then give a concrete fix.
- Be thorough and precise — avoid vague advice like "consider improving" without concrete steps.
- Include a fenced code snippet (3–8 lines) from the changed code between the issue and fix paragraphs.
- Name exact symbols, functions, fields, queries, or patterns to fix.
- Max 8 inline comments total. Prefer inline comments over summary.
- Use exact file paths from the diffs.
- `line` MUST match the numbered new file view (left column). Double-check before returning.
- `code_snippet` MUST be copied exactly from that numbered line — it anchors the inline comment.
- Only comment on changed lines when possible.
- Do not wrap the JSON response in markdown fences.

Files:
{chr(10).join(file_blocks)}
"""

    def _call_llm(self, prompt: str, detected_frameworks: list[str]) -> str:
        framework_hint = (
            f" Apply idiomatic review for detected stacks: {', '.join(detected_frameworks)}."
            if detected_frameworks
            else ""
        )
        return call_chat_completion(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict senior staff engineer doing thorough pre-merge PR reviews. "
                        "Return only valid JSON. Every comment must be specific and actionable with "
                        "a concrete fix in plain prose — no section labels like Problem → or "
                        "Specific fix →. Flag real issues; do not "
                        "return no_critical_issues if any actionable problem exists. Check logic "
                        "against work items, efficiency, framework idioms"
                        f"{framework_hint}, and Python PEP rules. "
                        "Never mention AI or automation. Never compliment the author."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=self.reasoning_effort,
        )

    def _parse_response(self, raw: str, file_diffs: list[FileDiff]) -> ReviewResult:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        payload = json.loads(text)
        llm_inline_items = payload.get("inline_comments", [])
        llm_verdict = str(payload.get("verdict", "no_critical_issues"))
        diffs_by_path = {item.path: item for item in file_diffs}
        diffs_by_basename = {item.path.rsplit("/", 1)[-1]: item for item in file_diffs}

        inline_comments: list[InlineComment] = []
        drop_reasons: list[str] = []
        for index, item in enumerate(llm_inline_items[:8], start=1):
            path = normalize_repo_path(str(item.get("file_path", "")))
            try:
                line = int(item.get("line", 0))
            except (TypeError, ValueError):
                line = 0
            code_snippet = str(item.get("code_snippet", "")).strip() or None
            content = _normalize_comment_content(str(item.get("content", "")))

            if not path or not line or not content:
                drop_reasons.append(
                    f"comment #{index}: missing file_path, line, or content "
                    f"(path={path!r}, line={line})"
                )
                continue

            file_diff = diffs_by_path.get(path) or diffs_by_basename.get(path.rsplit("/", 1)[-1])
            if file_diff is None:
                drop_reasons.append(
                    f"comment #{index}: file_path {path!r} not found in PR diff"
                )
                continue

            resolved_line, offset_start, offset_end = resolve_comment_position(
                new_content=file_diff.new_content,
                changed_lines=file_diff.changed_lines,
                requested_line=line,
                code_snippet=code_snippet,
            )

            inline_comments.append(
                InlineComment(
                    file_path=file_diff.path,
                    line=resolved_line,
                    content=content,
                    change_tracking_id=file_diff.change_tracking_id,
                    iteration_id=file_diff.iteration_id,
                    offset_start=offset_start,
                    offset_end=offset_end,
                )
            )

        summary = _normalize_comment_content(str(payload.get("summary", "")))
        if summary.lower().startswith("## automated"):
            summary = ""

        warnings = self._build_warnings(
            llm_verdict=llm_verdict,
            llm_inline_count=len(llm_inline_items),
            parsed_inline_count=len(inline_comments),
            drop_reasons=drop_reasons,
            has_summary=bool(summary),
        )
        for warning in warnings:
            logger.warning("Review consistency warning: %s", warning)
        for reason in drop_reasons:
            logger.warning("Dropped inline review comment: %s", reason)

        diagnostics = ReviewDiagnostics(
            llm_verdict=llm_verdict,
            llm_inline_count=len(llm_inline_items),
            parsed_inline_count=len(inline_comments),
            dropped_inline_count=len(drop_reasons),
            drop_reasons=drop_reasons,
            warnings=warnings,
            raw_llm_response=raw,
        )

        return ReviewResult(
            summary=summary,
            inline_comments=inline_comments,
            verdict=llm_verdict,
            detected_frameworks=[],
            diagnostics=diagnostics,
        )

    @staticmethod
    def _build_warnings(
        *,
        llm_verdict: str,
        llm_inline_count: int,
        parsed_inline_count: int,
        drop_reasons: list[str],
        has_summary: bool,
    ) -> list[str]:
        warnings: list[str] = []

        if llm_inline_count > 0 and parsed_inline_count == 0:
            warnings.append(
                f"LLM returned {llm_inline_count} inline comment(s) but all were "
                "dropped during parsing — review may look clean incorrectly."
            )
        elif drop_reasons:
            warnings.append(
                f"LLM returned {llm_inline_count} inline comment(s); "
                f"{len(drop_reasons)} dropped, {parsed_inline_count} kept."
            )

        if llm_verdict == "critical" and parsed_inline_count == 0 and not has_summary:
            warnings.append(
                "LLM verdict was 'critical' but no comments or summary will be posted."
            )

        if llm_verdict == "no_critical_issues" and llm_inline_count > 0:
            warnings.append(
                "LLM verdict was 'no_critical_issues' but inline comments were also returned."
            )

        if (
            llm_verdict == "no_critical_issues"
            and parsed_inline_count == 0
            and not has_summary
            and llm_inline_count == 0
        ):
            warnings.append(
                "LLM returned a clean verdict with no comments. If the PR looked "
                "suspicious, re-check whether findings were suppressed by over-filtering."
            )

        return warnings

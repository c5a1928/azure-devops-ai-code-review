from __future__ import annotations

import json
import logging
from app.services.git.types import FileDiff, PullRequestContext, ReviewThread
from app.services.openai_chat import call_chat_completion

logger = logging.getLogger(__name__)


class CommentResolver:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        reasoning_effort: str | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort

    def threads_to_resolve(
        self,
        pr: PullRequestContext,
        file_diffs: list[FileDiff],
        active_threads: list[ReviewThread],
    ) -> list[int]:
        if not active_threads:
            return []

        prompt = self._build_prompt(pr, file_diffs, active_threads)
        raw = self._call_llm(prompt)
        logger.info("LLM comment-resolution raw response:\n%s", raw)
        return self._parse_response(raw, active_threads)

    def _build_prompt(
        self,
        pr: PullRequestContext,
        file_diffs: list[FileDiff],
        active_threads: list[ReviewThread],
    ) -> str:
        thread_blocks = []
        for thread in active_threads:
            location = (
                f"{thread.file_path}:{thread.line}"
                if thread.file_path and thread.line
                else "PR-level"
            )
            thread_blocks.append(
                f"- thread_id: {thread.thread_id}\n  location: {location}\n  comment: {thread.content}"
            )

        diff_blocks = []
        for item in file_diffs:
            diff_blocks.append(f"### {item.path}\n```diff\n{item.diff}\n```")

        return f"""You are checking whether earlier pull request review comments have been addressed.

Pull request: {pr.title}

Existing active review threads:
{chr(10).join(thread_blocks)}

Current PR diffs:
{chr(10).join(diff_blocks) if diff_blocks else "(no file diffs)"}

Return ONLY valid JSON:
{{
  "resolve_thread_ids": [123, 456]
}}

Rules:
- Include a thread ID only when the underlying issue is clearly fixed in the current diff or code state.
- If the issue is still present, partially fixed, or uncertain, do NOT include the thread ID.
- Do not resolve threads just because the line changed; resolve only when the concern itself is addressed.
- Prefer false negatives over false positives.
- If nothing is resolved, return an empty array.
- Do not wrap JSON in markdown fences.
"""

    def _call_llm(self, prompt: str) -> str:
        return call_chat_completion(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You determine which PR review threads can be marked resolved. "
                        "Return only valid JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            reasoning_effort=self.reasoning_effort,
        )

    def _parse_response(self, raw: str, active_threads: list[ReviewThread]) -> list[int]:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        payload = json.loads(text)
        valid_ids = {thread.thread_id for thread in active_threads}
        resolved: list[int] = []
        for thread_id in payload.get("resolve_thread_ids", []):
            try:
                numeric_id = int(thread_id)
            except (TypeError, ValueError):
                continue
            if numeric_id in valid_ids:
                resolved.append(numeric_id)
        return resolved

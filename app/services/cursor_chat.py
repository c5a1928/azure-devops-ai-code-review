from __future__ import annotations

import logging
import tempfile
import time
from typing import Any

from app.services.openai_chat import DEFAULT_MAX_RETRIES, ChatCompletionError

logger = logging.getLogger(__name__)

DEFAULT_CURSOR_MODEL = "composer-2.5"


def _combine_messages(messages: list[dict[str, str]]) -> str:
    system_parts = [item["content"] for item in messages if item.get("role") == "system"]
    user_parts = [item["content"] for item in messages if item.get("role") == "user"]
    blocks: list[str] = []
    if system_parts:
        blocks.append("System instructions:\n" + "\n\n".join(system_parts))
    if user_parts:
        blocks.append("Task:\n" + "\n\n".join(user_parts))
    return "\n\n".join(blocks).strip()


def _is_retryable(exc: Exception) -> bool:
    retryable = getattr(exc, "is_retryable", None)
    if isinstance(retryable, bool):
        return retryable
    message = str(exc).lower()
    return "rate limit" in message or "429" in message or "too many requests" in message


def _retry_delay(exc: Exception, attempt: int) -> float:
    retry_after = getattr(exc, "retry_after", None)
    if isinstance(retry_after, (int, float)) and retry_after > 0:
        return min(float(retry_after), 120.0)
    return min(5.0 * (2**attempt), 120.0)


def call_cursor_completion(
    *,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    try:
        from cursor_sdk import Agent, AgentOptions, LocalAgentOptions
    except ImportError as exc:
        raise ChatCompletionError(
            0,
            "cursor-sdk",
            "cursor-sdk is not installed. Rebuild the Docker image after pulling latest code.",
        ) from exc

    prompt = _combine_messages(messages)
    if not prompt:
        raise ChatCompletionError(0, "cursor", "No prompt content provided.")

    model_id = (model or DEFAULT_CURSOR_MODEL).strip() or DEFAULT_CURSOR_MODEL
    last_error: ChatCompletionError | None = None

    for attempt in range(max_retries):
        try:
            result = Agent.prompt(
                prompt,
                AgentOptions(
                    api_key=api_key,
                    model=model_id,
                    local=LocalAgentOptions(cwd=tempfile.gettempdir()),
                ),
            )
            status = str(getattr(result, "status", "") or "")
            if status and status not in {"finished", "completed"}:
                message = f"Cursor agent finished with status '{status}'"
                if _is_retryable(RuntimeError(message)) and attempt < max_retries - 1:
                    time.sleep(_retry_delay(RuntimeError(message), attempt))
                    continue
                raise ChatCompletionError(0, "cursor", message)

            text = str(getattr(result, "result", "") or "").strip()
            if not text:
                raise ChatCompletionError(0, "cursor", "Cursor agent returned an empty response.")
            return text
        except ChatCompletionError:
            raise
        except Exception as exc:
            if _is_retryable(exc) and attempt < max_retries - 1:
                delay = _retry_delay(exc, attempt)
                logger.warning(
                    "Cursor API error (attempt %s/%s); retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)
                continue
            message = str(exc) or type(exc).__name__
            raise ChatCompletionError(0, "cursor", message) from exc

    if last_error is not None:
        raise last_error
    raise ChatCompletionError(0, "cursor", "Cursor request failed after retries")

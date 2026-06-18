from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
DEFAULT_MAX_RETRIES = 6
DEFAULT_TIMEOUT_SECONDS = 300


class ChatCompletionError(RuntimeError):
    def __init__(self, status_code: int, url: str, message: str) -> None:
        self.status_code = status_code
        self.url = url
        super().__init__(f"LLM API error {status_code} for {url}: {message}")


def build_chat_completion_body(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    effort = (reasoning_effort or "").strip().lower()
    if effort:
        body["reasoning_effort"] = effort
        # Reasoning models count internal reasoning tokens toward this limit.
        body["max_completion_tokens"] = max_tokens
    else:
        body["temperature"] = temperature
        body["max_tokens"] = max_tokens
    return body


def _retry_delay_seconds(exc: urllib.error.HTTPError, attempt: int) -> float:
    retry_after = exc.headers.get("Retry-After") if exc.headers else None
    if retry_after:
        try:
            return min(max(float(retry_after), 1.0), 120.0)
        except ValueError:
            pass
    return min(5.0 * (2**attempt), 120.0)


def _read_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode(errors="replace")[:2000]
    except Exception:
        return str(exc.reason or exc)


def call_chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> str:
    url = f"{base_url.rstrip('/')}/chat/completions"
    body = build_chat_completion_body(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    payload = json.dumps(body).encode()
    last_error: ChatCompletionError | None = None

    for attempt in range(max_retries):
        req = urllib.request.Request(url, data=payload, method="POST")
        req.add_header("Authorization", f"Bearer {api_key}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            error_body = _read_error_body(exc)
            if exc.code in RETRYABLE_STATUS_CODES and attempt < max_retries - 1:
                delay = _retry_delay_seconds(exc, attempt)
                logger.warning(
                    "LLM API returned %s (attempt %s/%s); retrying in %.1fs",
                    exc.code,
                    attempt + 1,
                    max_retries,
                    delay,
                )
                time.sleep(delay)
                continue
            if exc.code == 429:
                message = (
                    error_body
                    or "Too Many Requests — rate or token limit exceeded. "
                    "Wait a minute and retry, or use a smaller PR / lower max tokens."
                )
            else:
                message = error_body or str(exc.reason or exc)
            raise ChatCompletionError(exc.code, url, message) from exc
        except urllib.error.URLError as exc:
            if attempt < max_retries - 1:
                delay = min(5.0 * (2**attempt), 60.0)
                logger.warning(
                    "LLM API connection error (attempt %s/%s); retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries,
                    delay,
                    exc.reason,
                )
                time.sleep(delay)
                continue
            raise ChatCompletionError(0, url, str(exc.reason)) from exc

        choices = data.get("choices") or []
        if not choices:
            message = json.dumps(data)[:2000]
            last_error = ChatCompletionError(0, url, f"Empty choices in response: {message}")
            if attempt < max_retries - 1:
                time.sleep(min(5.0 * (2**attempt), 30.0))
                continue
            raise last_error

        content = choices[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content.strip():
            message = json.dumps(data)[:2000]
            last_error = ChatCompletionError(0, url, f"Missing message content: {message}")
            if attempt < max_retries - 1:
                time.sleep(min(5.0 * (2**attempt), 30.0))
                continue
            raise last_error
        return content

    if last_error is not None:
        raise last_error
    raise ChatCompletionError(0, url, "LLM request failed after retries")

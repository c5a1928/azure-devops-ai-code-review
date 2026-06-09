from __future__ import annotations

import json
import urllib.request
from typing import Any


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


def call_chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None,
) -> str:
    body = build_chat_completion_body(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode(),
        method="POST",
    )
    req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    return data["choices"][0]["message"]["content"]

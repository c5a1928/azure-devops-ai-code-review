from __future__ import annotations

from app.services.cursor_chat import call_cursor_completion
from app.services.openai_chat import call_chat_completion


def call_llm_completion(
    *,
    llm_provider: str,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str | None = None,
) -> str:
    provider = (llm_provider or "openai").strip().lower()
    if provider == "cursor":
        return call_cursor_completion(
            api_key=api_key,
            model=model,
            messages=messages,
        )
    return call_chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
    )

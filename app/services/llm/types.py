from __future__ import annotations

LLM_PROVIDERS = frozenset({"openai", "cursor", "anthropic", "gemini", "llama", "custom"})

LLM_PROVIDER_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "cursor": "Cursor",
    "anthropic": "Anthropic",
    "gemini": "Gemini",
    "llama": "Llama",
    "custom": "Custom",
}

LLM_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-5.5",
        "token_label": "OpenAI API key",
    },
    "cursor": {
        "base_url": "",
        "default_model": "composer-2.5",
        "token_label": "Cursor API key",
    },
    "anthropic": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-sonnet-4",
        "token_label": "API key",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "default_model": "gemini-2.0-flash",
        "token_label": "Google AI API key",
    },
    "llama": {
        "base_url": "http://localhost:11434/v1",
        "default_model": "llama3.2",
        "token_label": "API key",
    },
    "custom": {
        "base_url": "",
        "default_model": "",
        "token_label": "API key",
    },
}

LLM_PROVIDER_BASE_URL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "openai": [
        {"label": "OpenAI", "url": "https://api.openai.com/v1"},
        {
            "label": "Azure OpenAI",
            "url": "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
        },
    ],
    "cursor": [],
    "anthropic": [
        {"label": "OpenRouter", "url": "https://openrouter.ai/api/v1"},
        {
            "label": "Anthropic-compatible proxy",
            "url": "https://your-proxy.example.com/v1",
        },
    ],
    "gemini": [
        {
            "label": "Google AI (OpenAI compatible)",
            "url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        },
    ],
    "llama": [
        {"label": "Ollama (local)", "url": "http://localhost:11434/v1"},
        {"label": "Groq", "url": "https://api.groq.com/openai/v1"},
        {"label": "OpenRouter", "url": "https://openrouter.ai/api/v1"},
    ],
    "custom": [],
}

LLM_PROVIDER_MODEL_OPTIONS: dict[str, list[dict[str, str]]] = {
    "openai": [
        {"label": "GPT-5.5 — best review quality", "id": "gpt-5.5"},
        {"label": "GPT-5.4 mini — balanced", "id": "gpt-5.4-mini"},
        {"label": "GPT-4o", "id": "gpt-4o"},
        {"label": "GPT-4o mini — fast & cheap", "id": "gpt-4o-mini"},
        {"label": "o3-mini — reasoning", "id": "o3-mini"},
    ],
    "cursor": [
        {"label": "Composer 2.5 — recommended", "id": "composer-2.5"},
        {"label": "Composer 2", "id": "composer-2"},
        {"label": "GPT-5.4", "id": "gpt-5.4"},
        {"label": "Claude Sonnet 4.6", "id": "claude-sonnet-4.6"},
    ],
    "anthropic": [
        {"label": "Claude Sonnet 4", "id": "anthropic/claude-sonnet-4"},
        {"label": "Claude 3.7 Sonnet", "id": "anthropic/claude-3.7-sonnet"},
        {"label": "Claude 3.5 Sonnet", "id": "anthropic/claude-3.5-sonnet"},
        {"label": "Claude 3.5 Haiku — fast", "id": "anthropic/claude-3.5-haiku"},
    ],
    "gemini": [
        {"label": "Gemini 2.0 Flash", "id": "gemini-2.0-flash"},
        {"label": "Gemini 2.0 Flash Lite", "id": "gemini-2.0-flash-lite"},
        {"label": "Gemini 1.5 Pro", "id": "gemini-1.5-pro"},
    ],
    "llama": [
        {"label": "Llama 3.3 70B (Groq)", "id": "llama-3.3-70b-versatile"},
        {"label": "Llama 3.2 (Ollama)", "id": "llama3.2"},
        {"label": "Llama 3.3 70B (OpenRouter)", "id": "meta-llama/llama-3.3-70b-instruct"},
    ],
    "custom": [],
}


def infer_llm_provider(base_url: str, model: str) -> str:
    url = base_url.strip().lower()
    model_id = model.strip().lower()

    for provider_id in ("openai", "cursor", "anthropic", "gemini", "llama"):
        for option in LLM_PROVIDER_BASE_URL_OPTIONS[provider_id]:
            if option["url"].lower() == url:
                return provider_id
        for option in LLM_PROVIDER_MODEL_OPTIONS[provider_id]:
            if option["id"].lower() == model_id:
                return provider_id

    if "api.openai.com" in url or "openai.azure.com" in url:
        return "openai"
    if "generativelanguage.googleapis.com" in url or model_id.startswith("gemini"):
        return "gemini"
    if "groq.com" in url or ":11434" in url or "llama" in model_id:
        return "llama"
    if "anthropic" in model_id or "claude" in model_id:
        return "anthropic"

    if model_id.startswith("composer") or model_id.startswith("crsr"):
        return "cursor"

    return "custom"

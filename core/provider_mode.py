"""Provider mode detection — single source of truth.

Returns: "real" | "mock" | "invalid"
"""

import os


def detect_provider_mode() -> str:
    """Detect current provider mode.

    real: API key + base URL + model all present.
    mock/test: Explicit offline mode only.
    invalid: Partial configuration (e.g. key but no model).
    """
    explicit_mode = os.getenv("AI_LAB_PROVIDER_MODE", "").strip().lower()
    if explicit_mode in {"mock", "test"}:
        return explicit_mode
    if explicit_mode not in {"", "real"}:
        return "invalid"

    # Support both old and new env var names
    api_key = os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("AI_LAB_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("AI_LAB_LLM_MODEL") or os.getenv("OPENAI_MODEL", "")

    has_key = bool(api_key) and len(api_key) > 10 and "your_" not in api_key.lower()
    has_url = bool(base_url)
    has_model = bool(model)

    if not has_key:
        return "invalid"

    if not has_url:
        return "invalid"  # key but no URL
    if not has_model:
        return "invalid"  # key + URL but no model

    return "real"


def get_provider_info() -> dict:
    """Get provider info for display. Hides API key."""
    mode = detect_provider_mode()
    api_key = os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = os.getenv("AI_LAB_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    model = os.getenv("AI_LAB_LLM_MODEL") or os.getenv("OPENAI_MODEL", "")

    # Mask API key
    masked_key = ""
    if api_key and len(api_key) > 8:
        masked_key = api_key[:3] + "****" + api_key[-4:]

    return {
        "mode": mode,
        "provider": "OpenAI Compatible",
        "base_url": base_url or "N/A",
        "model": model or "N/A",
        "api_key_masked": masked_key,
    }

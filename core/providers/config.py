"""Provider configuration helpers.

Loads provider settings from environment or YAML config.
"""

from __future__ import annotations

from typing import Any

from core.providers.models import ProviderConfig, ProviderType


def default_configs() -> list[ProviderConfig]:
    """Return default provider configurations.

    Mock providers are always enabled for testing.
    Real providers (OpenAI, Chroma) are enabled but will gracefully
    degrade if API keys are not configured.
    """
    return [
        # LLM providers
        ProviderConfig(
            provider_type=ProviderType.LLM,
            provider_name="mock",
            priority=0,
        ),
        ProviderConfig(
            provider_type=ProviderType.LLM,
            provider_name="openai",
            priority=10,
        ),
        # Embedding providers
        ProviderConfig(
            provider_type=ProviderType.EMBEDDING,
            provider_name="mock",
            priority=0,
        ),
        ProviderConfig(
            provider_type=ProviderType.EMBEDDING,
            provider_name="openai",
            priority=10,
        ),
        # Vector providers
        ProviderConfig(
            provider_type=ProviderType.VECTOR,
            provider_name="mock",
            priority=0,
        ),
        ProviderConfig(
            provider_type=ProviderType.VECTOR,
            provider_name="chroma",
            priority=10,
        ),
        # Storage providers
        ProviderConfig(
            provider_type=ProviderType.STORAGE,
            provider_name="mock",
            priority=0,
        ),
    ]

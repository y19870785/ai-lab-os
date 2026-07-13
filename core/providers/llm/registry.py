"""LLM provider registration helpers."""

from __future__ import annotations

from core.providers.llm.protocol import LLMProvider
from core.providers.llm.mock import MockLLMProvider
from core.providers.llm.openai import OpenAILLMProvider
from core.providers.models import ProviderType
from core.providers.registry import ProviderRegistry


def register_builtin_llm_providers(registry: ProviderRegistry) -> None:
    """Register built-in LLM providers to the registry."""
    registry.register(ProviderType.LLM, "mock", MockLLMProvider)
    registry.register(ProviderType.LLM, "openai", OpenAILLMProvider)

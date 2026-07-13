"""Embedding provider registration helpers."""

from __future__ import annotations

from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.embedding.mock import MockEmbeddingProvider
from core.providers.embedding.openai import OpenAIEmbeddingProvider
from core.providers.models import ProviderType
from core.providers.registry import ProviderRegistry


def register_builtin_embedding_providers(registry: ProviderRegistry) -> None:
    """Register built-in embedding providers."""
    registry.register(ProviderType.EMBEDDING, "mock", MockEmbeddingProvider)
    registry.register(ProviderType.EMBEDDING, "openai", OpenAIEmbeddingProvider)

"""Vector provider registration helpers."""

from __future__ import annotations

from core.providers.vector.protocol import VectorProvider
from core.providers.vector.mock import MockVectorProvider
from core.providers.vector.chroma import ChromaVectorProvider
from core.providers.models import ProviderType
from core.providers.registry import ProviderRegistry


def register_builtin_vector_providers(registry: ProviderRegistry) -> None:
    """Register built-in vector providers."""
    registry.register(ProviderType.VECTOR, "mock", MockVectorProvider)
    registry.register(ProviderType.VECTOR, "chroma", ChromaVectorProvider)

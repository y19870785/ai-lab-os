"""ProviderFactory 鈥?configuration-driven provider creation.

Central factory that loads configurations and wires up providers.
Business code calls ProviderFactory, never instantiates providers directly.

Usage:
    factory = ProviderFactory(registry)
    factory.register_builtins()           # Registers mock + real providers
    configs = default_configs()           # Load from YAML/env
    await factory.initialize_all(configs)
    provider = factory.get(ProviderType.LLM)
"""

from __future__ import annotations

from typing import Any

from core.providers.base import BaseProvider
from core.providers.models import ProviderConfig, ProviderType
from core.providers.registry import ProviderRegistry
from core.providers.exceptions import ProviderConfigurationError
from core.providers.config import default_configs


class ProviderFactory:
    """Configuration-driven provider factory.

    Responsibilities:
    1. Register built-in provider classes (from registry modules)
    2. Load provider configurations
    3. Filter by enabled/priority
    4. Initialize lifecycles

    Does NOT:
    - Call external APIs
    - Parse API keys (that''s the config layer''s job)
    """

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry

    # 鈹€鈹€ Built-in registration 鈹€鈹€

    def register_builtins(self) -> None:
        """Register all built-in (mock + real) provider classes."""
        from core.providers.llm.registry import register_builtin_llm_providers
        from core.providers.embedding.registry import register_builtin_embedding_providers
        from core.providers.vector.registry import register_builtin_vector_providers
        from core.providers.storage.registry import register_builtin_storage_providers

        register_builtin_llm_providers(self._registry)
        register_builtin_embedding_providers(self._registry)
        register_builtin_vector_providers(self._registry)
        register_builtin_storage_providers(self._registry)

    # 鈹€鈹€ Initialization 鈹€鈹€

    async def initialize_all(self, configs: list[ProviderConfig] | None = None) -> list[BaseProvider]:
        """Initialize all enabled providers from configs.

        Args:
            configs: List of ProviderConfig. If None, uses default_configs().

        Returns:
            List of successfully initialized providers.
            Real providers that fail to initialize (e.g. no API key)
            are skipped gracefully; Mock providers always succeed.
        """
        if configs is None:
            configs = default_configs()

        # Sort by priority (higher = first)
        enabled = sorted(
            [c for c in configs if c.enabled],
            key=lambda c: c.priority,
            reverse=True,
        )

        initialized = []
        for config in enabled:
            try:
                provider = self._registry.get(config.provider_type, config.provider_name)
                await provider.initialize()
                initialized.append(provider)
            except Exception:
                # Real providers may fail due to missing API keys.
                # Skip gracefully so Mock providers remain available.
                pass

        return initialized

    # 鈹€鈹€ Convenience access 鈹€鈹€

    def get(self, provider_type: ProviderType, name: str = "") -> BaseProvider:
        """Get a ready provider. Raises if not initialized."""
        return self._registry.get(provider_type, name)

    def get_llm(self, name: str = "") -> "LLMProvider":
        from core.providers.llm.protocol import LLMProvider
        # Try real first, fall back to mock
        if not name:
            if self._registry.exists(ProviderType.LLM, "openai"):
                try:
                    p = self._registry.get(ProviderType.LLM, "openai")
                    if p.is_available():
                        return p  # type: ignore
                except Exception:
                    pass
        return self._registry.get(ProviderType.LLM, name or "mock")  # type: ignore

    def get_embedding(self, name: str = "") -> "EmbeddingProvider":
        from core.providers.embedding.protocol import EmbeddingProvider
        if not name:
            if self._registry.exists(ProviderType.EMBEDDING, "openai"):
                try:
                    p = self._registry.get(ProviderType.EMBEDDING, "openai")
                    if p.is_available():
                        return p  # type: ignore
                except Exception:
                    pass
        return self._registry.get(ProviderType.EMBEDDING, name or "mock")  # type: ignore

    def get_vector(self, name: str = "") -> "VectorProvider":
        from core.providers.vector.protocol import VectorProvider
        if not name:
            if self._registry.exists(ProviderType.VECTOR, "chroma"):
                try:
                    p = self._registry.get(ProviderType.VECTOR, "chroma")
                    if p.is_available():
                        return p  # type: ignore
                except Exception:
                    pass
        return self._registry.get(ProviderType.VECTOR, name or "mock")  # type: ignore

    def get_storage(self, name: str = "") -> "StorageProvider":
        from core.providers.storage.protocol import StorageProvider
        return self._registry.get(ProviderType.STORAGE, name or "mock")  # type: ignore

    @property
    def registry(self) -> ProviderRegistry:
        return self._registry

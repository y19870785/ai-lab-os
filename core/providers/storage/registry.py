"""Storage provider registration helpers."""

from __future__ import annotations

from core.providers.storage.protocol import StorageProvider
from core.providers.storage.mock import MockStorageProvider
from core.providers.models import ProviderType
from core.providers.registry import ProviderRegistry


def register_builtin_storage_providers(registry: ProviderRegistry) -> None:
    """Register built-in storage providers."""
    registry.register(ProviderType.STORAGE, "mock", MockStorageProvider)

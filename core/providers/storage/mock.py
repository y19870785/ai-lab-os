"""Mock Storage Provider using in-memory dict."""

from __future__ import annotations

from core.providers.storage.protocol import StorageProvider
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class MockStorageProvider(StorageProvider):
    """Mock storage using in-memory dict."""

    def __init__(self) -> None:
        info = ProviderInfo(
            provider_id="mock-sto-001",
            provider_type=ProviderType.STORAGE,
            name="mock",
            version="1.0.0",
            description="Mock storage provider",
            capabilities=[
                ProviderCapability(name="save", version="1.0"),
                ProviderCapability(name="load", version="1.0"),
            ],
        )
        super().__init__(info)
        self._store: dict[str, bytes] = {}
        self._meta: dict[str, dict] = {}

    async def _do_initialize(self) -> None:
        pass

    async def _do_shutdown(self) -> None:
        self._store.clear()
        self._meta.clear()

    async def _do_health_check(self) -> bool:
        return True

    async def save(self, key: str, data: bytes, metadata: dict | None = None) -> str:
        self._require_ready()
        self._store[key] = data
        if metadata:
            self._meta[key] = metadata
        return key

    async def load(self, key: str) -> bytes | None:
        self._require_ready()
        return self._store.get(key)

    async def delete(self, key: str) -> bool:
        self._require_ready()
        existed = key in self._store
        self._store.pop(key, None)
        self._meta.pop(key, None)
        return existed

    async def exists(self, key: str) -> bool:
        self._require_ready()
        return key in self._store

    async def list_keys(self, prefix: str = "") -> list[str]:
        self._require_ready()
        return [k for k in self._store if k.startswith(prefix)]

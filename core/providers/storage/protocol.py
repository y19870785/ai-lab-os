"""Storage Provider Protocol.

Unified interface for blob/file/key-value storage backends.
"""

from __future__ import annotations

from abc import abstractmethod

from core.providers.base import BaseProvider


class StorageProvider(BaseProvider):
    """Abstract storage backend.

    Maps to local filesystem / S3 / MinIO / GCS.
    """

    @abstractmethod
    async def save(self, key: str, data: bytes, metadata: dict | None = None) -> str:
        """Save data under key. Returns the key."""
        ...

    @abstractmethod
    async def load(self, key: str) -> bytes | None:
        """Load data by key. Returns None if not found."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete data by key. Returns True if existed."""
        ...

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        ...

    @abstractmethod
    async def list_keys(self, prefix: str = "") -> list[str]:
        """List keys with optional prefix filter."""
        ...

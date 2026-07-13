"""Storage Provider sub-module."""
from core.providers.storage.protocol import StorageProvider
from core.providers.storage.mock import MockStorageProvider

__all__ = ["StorageProvider", "MockStorageProvider"]

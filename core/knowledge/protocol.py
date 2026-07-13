"""KnowledgeStore — abstract storage interface.

Aligns with MemoryStore protocol (8-method interface).
All knowledge persistence goes through this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.knowledge.models import KnowledgeItem, KnowledgeQuery, KnowledgeResult


class KnowledgeStore(ABC):
    """Abstract knowledge storage backend.

    Same 8-method signature as MemoryStore for consistency.
    """

    @abstractmethod
    async def save(self, item: KnowledgeItem) -> str:
        """Store a knowledge item. Returns item ID."""
        ...

    @abstractmethod
    async def batch_save(self, items: list[KnowledgeItem]) -> list[str]:
        """Batch store knowledge items. Returns IDs."""
        ...

    @abstractmethod
    async def get(self, id: str) -> KnowledgeItem | None:
        """Retrieve a knowledge item by ID."""
        ...

    @abstractmethod
    async def query(self, spec: KnowledgeQuery) -> list[KnowledgeResult]:
        """Search for knowledge items."""
        ...

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a knowledge item by ID."""
        ...

    @abstractmethod
    async def count(self) -> int:
        """Total knowledge items."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize storage (idempotent)."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release resources (idempotent)."""
        ...

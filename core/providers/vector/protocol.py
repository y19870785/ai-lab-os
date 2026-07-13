"""Vector Provider Protocol.

Unified interface for vector database backends.
Supports collection-based CRUD and similarity search.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from core.providers.base import BaseProvider


class VectorRecord(BaseModel):
    """A single vector record with metadata."""
    id: str
    vector: list[float]
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorSearchResult(BaseModel):
    """A single search result with score."""
    id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class VectorSearchQuery(BaseModel):
    """Search query parameters."""
    vector: list[float]
    top_k: int = 10
    filter: dict[str, Any] | None = None
    min_score: float = 0.0


class VectorProvider(BaseProvider):
    """Abstract vector database backend.

    Maps naturally to Chroma / Qdrant / Milvus / FAISS.
    """

    @abstractmethod
    async def insert(self, collection: str, records: list[VectorRecord]) -> list[str]:
        """Insert records into a collection. Returns inserted IDs."""
        ...

    @abstractmethod
    async def search(self, collection: str, query: VectorSearchQuery) -> list[VectorSearchResult]:
        """Search for nearest neighbors in a collection."""
        ...

    @abstractmethod
    async def delete(self, collection: str, ids: list[str]) -> int:
        """Delete records by ID. Returns count deleted."""
        ...

    @abstractmethod
    async def update(self, collection: str, record: VectorRecord) -> bool:
        """Update a record (upsert). Returns True on success."""
        ...

    @abstractmethod
    async def collection_info(self, collection: str) -> dict[str, Any]:
        """Return collection metadata (count, dimension, etc.)."""
        ...

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """List all collection names."""
        ...

    @abstractmethod
    async def delete_collection(self, collection: str) -> bool:
        """Delete an entire collection."""
        ...

"""VectorStore abstract interface.

Reserved vector search abstraction layer.
Future implementations: ChromaDB / FAISS / Milvus / Pinecone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.memory.models import MemoryItem, MemoryQuery


class VectorStore(ABC):
    """Vector database abstract interface."""

    @abstractmethod
    async def insert(self, item: MemoryItem) -> str:
        ...

    @abstractmethod
    async def batch_insert(self, items: list[MemoryItem]) -> list[str]:
        ...

    @abstractmethod
    async def search(self, query: MemoryQuery) -> list[MemoryItem]:
        ...

    @abstractmethod
    async def delete(self, id: str) -> bool:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...

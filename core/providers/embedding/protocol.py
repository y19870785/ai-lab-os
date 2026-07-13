"""Embedding Provider Protocol.

Unified interface for text-to-vector embedding backends.
"""

from __future__ import annotations

from abc import abstractmethod

from core.providers.base import BaseProvider


class EmbeddingProvider(BaseProvider):
    """Abstract embedding backend.

    All embedding access goes through this interface.
    """

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Convert a batch of texts to embedding vectors.

        Returns one vector per input text, in the same order.
        """
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """Convert a single query text to a vector.

        May use different preprocessing than embed() (query vs doc).
        """
        ...

    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding vector dimension."""
        ...

    @abstractmethod
    def model_name(self) -> str:
        """Return the embedding model identifier."""
        ...

    @abstractmethod
    def normalize(self, vector: list[float]) -> list[float]:
        """Normalize a vector to unit length.

        Some providers include this in embed(); this is explicit.
        """
        ...

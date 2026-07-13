"""Embedding Provider sub-module."""
from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.embedding.mock import MockEmbeddingProvider

__all__ = ["EmbeddingProvider", "MockEmbeddingProvider"]

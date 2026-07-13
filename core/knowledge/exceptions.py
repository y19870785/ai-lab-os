"""Knowledge Layer exceptions."""

from __future__ import annotations


class KnowledgeError(Exception):
    """Base knowledge exception."""
    pass


class IngestionError(KnowledgeError):
    """Error during knowledge ingestion."""
    pass


class ChunkingError(KnowledgeError):
    """Error during document chunking."""
    pass


class RetrievalError(KnowledgeError):
    """Error during knowledge retrieval."""
    pass


class KnowledgeNotFoundError(KnowledgeError):
    """Knowledge item not found."""
    pass

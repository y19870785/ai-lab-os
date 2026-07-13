"""Knowledge Layer.

AI-Lab's unified knowledge management system.
Handles document ingestion, chunking, embedding, vector storage,
and hybrid retrieval — all through Provider Layer abstractions.

Usage:
    from core.knowledge import KnowledgeManager, KnowledgeItem, KnowledgeQuery

    manager = KnowledgeManager(store=my_store, embedding=emb, vector=vec)
    await manager.initialize()
    item, chunks = await manager.ingest("document text...", title="My Doc")
    results = await manager.search(KnowledgeQuery(text="query"))
"""

from core.knowledge.models import (
    KnowledgeItem, DocumentChunk, KnowledgeQuery, KnowledgeResult,
    KnowledgeType, SourceType, KnowledgeStats,
)
from core.knowledge.protocol import KnowledgeStore
from core.knowledge.manager import KnowledgeManager
from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.chunking import (
    ChunkStrategy, get_chunker,
    FixedLengthChunker, SentenceChunker, ParagraphChunker,
    MarkdownChunker, RecursiveChunker, TokenWindowChunker,
)
from core.knowledge.retrieval import KeywordRetriever, VectorRetriever, HybridRetriever
from core.knowledge.ranking import KnowledgeRanker, RankingConfig
from core.knowledge.config import KnowledgeConfig, ChunkingConfig, RetrievalConfig
from core.knowledge.metadata import MetadataExtractorRegistry, build_default_registry
from core.knowledge.filters import (
    by_type, by_source, by_tag, by_language, by_confidence, by_author, combine,
)
from core.knowledge.exceptions import (
    KnowledgeError, IngestionError, ChunkingError, RetrievalError, KnowledgeNotFoundError,
)

__all__ = [
    # Models
    "KnowledgeItem", "DocumentChunk", "KnowledgeQuery", "KnowledgeResult",
    "KnowledgeType", "SourceType", "KnowledgeStats",
    # Protocol
    "KnowledgeStore",
    # Manager
    "KnowledgeManager",
    # Ingestion
    "IngestionPipeline",
    # Chunking
    "ChunkStrategy", "get_chunker",
    "FixedLengthChunker", "SentenceChunker", "ParagraphChunker",
    "MarkdownChunker", "RecursiveChunker", "TokenWindowChunker",
    # Retrieval
    "KeywordRetriever", "VectorRetriever", "HybridRetriever",
    # Ranking
    "KnowledgeRanker", "RankingConfig",
    # Config
    "KnowledgeConfig", "ChunkingConfig", "RetrievalConfig",
    # Metadata
    "MetadataExtractorRegistry", "build_default_registry",
    # Filters
    "by_type", "by_source", "by_tag", "by_language", "by_confidence", "by_author", "combine",
    # Exceptions
    "KnowledgeError", "IngestionError", "ChunkingError", "RetrievalError", "KnowledgeNotFoundError",
]

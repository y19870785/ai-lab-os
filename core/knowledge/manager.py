"""KnowledgeManager — Knowledge Layer single entry point.

All Agent and Application code accesses knowledge through this manager.
No direct access to stores, retrievers, or providers.
"""

from __future__ import annotations

from typing import Any

from core.knowledge.models import (
    KnowledgeItem, DocumentChunk, KnowledgeQuery, KnowledgeResult, KnowledgeStats,
    KnowledgeType, SourceType,
)
from core.knowledge.protocol import KnowledgeStore
from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.retrieval import KeywordRetriever, VectorRetriever, HybridRetriever
from core.knowledge.ranking import KnowledgeRanker, RankingConfig
from core.knowledge.cache import KnowledgeCache
from core.knowledge.config import KnowledgeConfig, ChunkingConfig
from core.knowledge.chunking import get_chunker
from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.vector.protocol import VectorProvider


class KnowledgeManager:
    """Unified knowledge entry point.

    Usage:
        manager = KnowledgeManager(store=sqlite_store, embedding=emb, vector=vec)
        await manager.initialize()

        item, chunks = await manager.ingest("Some document text...", title="My Doc")
        results = await manager.search("query text")
        await manager.delete("item_id")
    """

    def __init__(
        self,
        store: KnowledgeStore,
        embedding_provider: EmbeddingProvider | None = None,
        vector_provider: VectorProvider | None = None,
        config: KnowledgeConfig | None = None,
        bus=None,
    ) -> None:
        self._store = store
        self._embedding = embedding_provider
        self._vector = vector_provider
        self._config = config or KnowledgeConfig()
        self._bus = bus

        # Pipeline
        self._pipeline = IngestionPipeline(
            chunker=get_chunker(self._config.chunking.strategy, **{
                "chunk_size": self._config.chunking.chunk_size,
                "overlap": self._config.chunking.chunk_overlap,
            }),
            embedding_provider=embedding_provider,
            vector_provider=vector_provider,
        )

        # Retrieval
        self._keyword = KeywordRetriever()
        self._vector_retriever: VectorRetriever | None = None
        if embedding_provider and vector_provider:
            self._vector_retriever = VectorRetriever(embedding_provider, vector_provider)
        self._hybrid = HybridRetriever(
            vector=self._vector_retriever or VectorRetriever(
                embedding_provider or _DummyEmbedding(),
                vector_provider or _DummyVector(),
            ),
            keyword=self._keyword,
            vector_weight=self._config.retrieval.vector_weight,
            keyword_weight=self._config.retrieval.keyword_weight,
        ) if self._config.retrieval.hybrid_enabled else None

        # Ranking
        self._ranker = KnowledgeRanker()

        # Cache
        self._cache = KnowledgeCache() if self._config.cache_enabled else None

        # Stats
        self._stats = KnowledgeStats()

    async def initialize(self) -> None:
        """Initialize the knowledge store."""
        await self._store.initialize()

    async def close(self) -> None:
        """Release resources."""
        await self._store.close()

    # ── Ingestion ──

    async def ingest(
        self,
        content: str,
        title: str = "",
        source: str = "",
        source_type: str = "plaintext",
        knowledge_type: str = "document",
        author: str = "",
        language: str = "",
        tags: list[str] | None = None,
    ) -> tuple[KnowledgeItem, list[DocumentChunk]]:
        """Ingest a document into the knowledge base.

        Returns (KnowledgeItem, list of DocumentChunks).
        """
        st = SourceType(source_type) if source_type else SourceType.PLAINTEXT
        kt = KnowledgeType(knowledge_type) if knowledge_type else KnowledgeType.DOCUMENT

        item, chunks = await self._pipeline.ingest(
            content=content, title=title, source=source,
            source_type=st, knowledge_type=kt,
            author=author, language=language, tags=tags,
        )

        # Save to store
        await self._store.save(item)
        self._stats.total_items += 1
        self._stats.total_chunks += len(chunks)

        # Update keyword index
        for chunk in chunks:
            self._keyword.index(KnowledgeItem(
                id=chunk.chunk_id,
                content=chunk.content,
                title=title,
                source=source,
                source_type=st,
                metadata={"document_id": item.id, "chunk_index": chunk.index},
            ))

        # Publish event
        if self._bus:
            await self._publish("knowledge.ingested", item.id, {
                "title": title, "chunk_count": len(chunks),
            })

        return item, chunks

    # ── Retrieval ──

    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        """Search knowledge base. Returns ranked results."""
        # Check cache
        if self._cache:
            cache_key = self._cache.make_key("search", query.text, str(query.top_k))
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        # Hybrid search
        if self._hybrid:
            results = await self._hybrid.search(query)
        else:
            # Fallback to keyword only
            kw_results = self._keyword.search(query.text, query.top_k)
            results = [(rid, score, None) for rid, score in kw_results]

        # Resolve items
        ranked = []
        for item_id, combined_score, vec_score in results:
            item = await self._store.get(item_id)
            if item is None:
                # Try chunk-level lookup
                item = KnowledgeItem(
                    id=item_id, content="", title="(chunk)",
                )
            ranked.append(KnowledgeResult(
                item=item, score=combined_score, rerank_score=vec_score,
            ))

        # Sort by score
        ranked.sort(key=lambda r: r.score, reverse=True)
        ranked = ranked[:query.top_k]

        # Cache
        if self._cache:
            self._cache.set(cache_key or "", ranked, self._config.cache_ttl)

        # Publish
        if self._bus:
            await self._publish("knowledge.retrieved", "", {
                "query": query.text, "result_count": len(ranked),
            })

        return ranked

    async def retrieve(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        """Alias for search()."""
        return await self.search(query)

    # ── CRUD ──

    async def get(self, item_id: str) -> KnowledgeItem | None:
        """Get a knowledge item by ID."""
        return await self._store.get(item_id)

    async def delete(self, item_id: str) -> bool:
        """Delete a knowledge item and its chunks."""
        result = await self._store.delete(item_id)
        self._keyword.remove(item_id)
        if result and self._bus:
            await self._publish("knowledge.deleted", item_id, {})
        return result

    # ── Maintenance ──

    async def reindex(self) -> int:
        """Rebuild the keyword index from store. Returns item count."""
        self._keyword = KeywordRetriever()
        # This requires full scan — store.query() with all items
        # For now, items are indexed during ingest()
        return self._keyword.doc_count

    async def statistics(self) -> KnowledgeStats:
        """Return current knowledge statistics."""
        self._stats.total_items = await self._store.count()
        return self._stats

    async def refresh(self) -> None:
        """Refresh caches and indexes."""
        if self._cache:
            self._cache.clear()

    # ── Events ──

    async def _publish(self, event_type: str, item_id: str, extra: dict[str, Any] | None = None) -> None:
        if not self._bus:
            return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type=event_type,
            memory_id=item_id,
            memory_type="knowledge",
            source="knowledge.manager",
            extra=extra or {},
        )
        await self._bus.publish(event_type, event)

    @property
    def store(self):
        return self._store


# ── Dummy providers for offline mode ──

class _DummyEmbedding:
    async def embed_query(self, query: str) -> list[float]:
        return [0.0] * 384

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384] * len(texts)


class _DummyVector:
    async def search(self, collection: str, query: Any) -> list:
        return []
    async def insert(self, collection: str, records: list) -> list:
        return []

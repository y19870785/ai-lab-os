"""Knowledge retrieval — Vector + Keyword + Hybrid.

All retrieval goes through Provider Layer:
- VectorProvider for vector search
- EmbeddingProvider for query embedding
- Keyword retrieval is pure Python (no external deps)
"""

from __future__ import annotations

import math
import re
from typing import Any

from core.knowledge.models import KnowledgeItem, KnowledgeQuery, KnowledgeResult
from core.providers.embedding.protocol import EmbeddingProvider
from core.providers.vector.protocol import VectorProvider, VectorSearchQuery


class KeywordRetriever:
    """Simple TF-IDF-like keyword retrieval.

    Uses term frequency in a local inverted index.
    """

    def __init__(self) -> None:
        self._index: dict[str, dict[str, int]] = {}  # term -> {item_id: tf}
        self._items: dict[str, KnowledgeItem] = {}
        self._doc_count = 0

    def index(self, item: KnowledgeItem) -> None:
        """Add a knowledge item to the keyword index."""
        terms = self._tokenize(item.content)
        self._doc_count += 1
        self._items[item.id] = item

        tf: dict[str, int] = {}
        for t in terms:
            tf[t] = tf.get(t, 0) + 1

        for term, count in tf.items():
            if term not in self._index:
                self._index[term] = {}
            self._index[term][item.id] = count

    def remove(self, item_id: str) -> None:
        """Remove an item from the keyword index."""
        if item_id in self._items:
            del self._items[item_id]
            self._doc_count -= 1
        for term_dict in self._index.values():
            term_dict.pop(item_id, None)

    def search(self, query_text: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search by keywords. Returns [(item_id, score), ...]."""
        if not self._doc_count or not query_text.strip():
            return []

        query_terms = self._tokenize(query_text)
        if not query_terms:
            return []

        scores: dict[str, float] = {}
        for term in query_terms:
            postings = self._index.get(term, {})
            idf = math.log((self._doc_count + 1) / (len(postings) + 1)) + 1
            for doc_id, tf in postings.items():
                scores[doc_id] = scores.get(doc_id, 0) + tf * idf

        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_scores[:top_k]

    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenizer — splits on non-alphanumeric, filters short tokens."""
        tokens_en = re.findall(r'[a-zA-Z0-9]+', text.lower())
        tokens_cn = re.findall(r'[\u4e00-\u9fff]', text)
        tokens = [t for t in tokens_en if len(t) >= 2] + tokens_cn
        return tokens

    @property
    def doc_count(self) -> int:
        return self._doc_count


class VectorRetriever:
    """Vector-based retrieval using Provider Layer."""

    def __init__(self, embedding_provider: EmbeddingProvider, vector_provider: VectorProvider,
                 collection: str = "knowledge") -> None:
        self._embedding = embedding_provider
        self._vector = vector_provider
        self._collection = collection

    async def search(self, query_text: str, top_k: int = 10,
                     filters: dict[str, Any] | None = None,
                     min_score: float = 0.0) -> list[tuple[str, float]]:
        """Vector search. Returns [(item_id, score), ...]."""
        query_vec = await self._embedding.embed_query(query_text)
        results = await self._vector.search(
            self._collection,
            VectorSearchQuery(vector=query_vec, top_k=top_k, filter=filters, min_score=min_score),
        )
        return [(r.id, r.score) for r in results]

    async def index_chunk(self, chunk_id: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Index a chunk into the vector store."""
        vec = await self._embedding.embed_query(content)
        from core.providers.vector.protocol import VectorRecord
        await self._vector.insert(self._collection, [
            VectorRecord(id=chunk_id, vector=vec, metadata=metadata or {}),
        ])


class HybridRetriever:
    """Combined vector + keyword retrieval with configurable weights."""

    def __init__(self, vector: VectorRetriever, keyword: KeywordRetriever,
                 vector_weight: float = 0.7, keyword_weight: float = 0.3) -> None:
        self._vector = vector
        self._keyword = keyword
        self._vw = vector_weight
        self._kw = keyword_weight

    async def search(self, query: KnowledgeQuery) -> list[tuple[str, float, float | None]]:
        """Hybrid search. Returns [(item_id, combined_score, vector_score), ...]."""
        # Run both searches in parallel (conceptually — use asyncio.gather in production)
        kw_results = self._keyword.search(query.text, query.top_k * 2)
        vec_results = await self._vector.search(query.text, query.top_k * 2, query.filters, query.min_score)

        # Merge and normalize
        kw_max = max((s for _, s in kw_results), default=1.0)
        vec_max = max((s for _, s in vec_results), default=1.0)

        combined: dict[str, tuple[float, float | None]] = {}

        for item_id, score in kw_results:
            combined[item_id] = (score / kw_max * self._kw, None)

        for item_id, score in vec_results:
            v_score = score / vec_max * self._vw
            if item_id in combined:
                prev_kw, _ = combined[item_id]
                combined[item_id] = (prev_kw + v_score, score)
            else:
                combined[item_id] = (v_score, score)

        sorted_results = sorted(combined.items(), key=lambda x: x[1][0], reverse=True)
        return [(item_id, c_score, v_score) for item_id, (c_score, v_score) in sorted_results[:query.top_k]]

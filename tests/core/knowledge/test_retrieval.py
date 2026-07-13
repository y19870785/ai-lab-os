"""Tests for retrieval — keyword, vector, hybrid."""
import pytest
from core.knowledge.models import KnowledgeItem, KnowledgeQuery
from core.knowledge.retrieval import KeywordRetriever
from core.providers.embedding.mock import MockEmbeddingProvider
from core.providers.vector.mock import MockVectorProvider


class TestKeywordRetriever:
    def test_index_and_search(self):
        kr = KeywordRetriever()
        item = KnowledgeItem(id="i1", title="Test", content="hello world python programming")
        kr.index(item)

        results = kr.search("python", top_k=5)
        assert len(results) == 1
        assert results[0][0] == "i1"
        assert results[0][1] > 0

    def test_no_match(self):
        kr = KeywordRetriever()
        item = KnowledgeItem(id="i1", content="hello world")
        kr.index(item)
        results = kr.search("nonexistent", top_k=5)
        assert results == []

    def test_multiple_items(self):
        kr = KeywordRetriever()
        kr.index(KnowledgeItem(id="a", content="python django"))
        kr.index(KnowledgeItem(id="b", content="python flask"))
        kr.index(KnowledgeItem(id="c", content="java spring"))

        results = kr.search("python", top_k=5)
        assert len(results) == 2
        ids = [r[0] for r in results]
        assert "a" in ids
        assert "b" in ids

    def test_remove(self):
        kr = KeywordRetriever()
        kr.index(KnowledgeItem(id="x", content="python"))
        kr.index(KnowledgeItem(id="y", content="java"))
        kr.remove("x")
        results = kr.search("python", top_k=5)
        assert results == []

    def test_chinese(self):
        kr = KeywordRetriever()
        kr.index(KnowledgeItem(id="c1", content="Python是一种编程语言"))
        results = kr.search("Python", top_k=5)
        assert len(results) == 1

    def test_empty_query(self):
        kr = KeywordRetriever()
        kr.index(KnowledgeItem(id="a", content="hello"))
        assert kr.search("", top_k=5) == []


class TestVectorRetriever:
    @pytest.mark.asyncio
    async def test_search(self):
        emb = MockEmbeddingProvider()
        await emb.initialize()
        vec = MockVectorProvider()
        await vec.initialize()

        from core.knowledge.retrieval import VectorRetriever
        vr = VectorRetriever(emb, vec, "test")

        # Index a chunk
        await vr.index_chunk("c1", "test query")

        results = await vr.search("test query", top_k=5)
        assert len(results) == 1
        assert results[0][0] == "c1"

"""Tests for KnowledgeManager (integration)."""
import pytest
from core.knowledge import KnowledgeManager, KnowledgeItem, KnowledgeQuery
from core.knowledge.protocol import KnowledgeStore
from core.knowledge.models import KnowledgeResult


class InMemoryKnowledgeStore(KnowledgeStore):
    """In-memory store for testing."""
    def __init__(self):
        self._items = {}

    async def save(self, item):
        self._items[item.id] = item
        return item.id

    async def batch_save(self, items):
        return [await self.save(i) for i in items]

    async def get(self, id):
        return self._items.get(id)

    async def query(self, spec):
        results = []
        for item in self._items.values():
            if spec.text.lower() in item.content.lower():
                results.append(KnowledgeResult(item=item, score=0.5))
        return results[:spec.top_k]

    async def delete(self, id):
        return self._items.pop(id, None) is not None

    async def count(self):
        return len(self._items)

    async def initialize(self):
        pass

    async def close(self):
        self._items.clear()


class TestKnowledgeManager:
    @pytest.mark.asyncio
    async def test_ingest_and_search(self):
        store = InMemoryKnowledgeStore()
        from core.providers.embedding.mock import MockEmbeddingProvider
        from core.providers.vector.mock import MockVectorProvider
        emb = MockEmbeddingProvider()
        await emb.initialize()
        vec = MockVectorProvider()
        await vec.initialize()

        manager = KnowledgeManager(store=store, embedding_provider=emb, vector_provider=vec)
        await manager.initialize()

        item, chunks = await manager.ingest(
            content="Python is a popular programming language for data science.",
            title="Python Guide",
            source="docs/python.md",
        )
        assert item.id
        assert len(chunks) >= 1

        # Search
        results = await manager.search(KnowledgeQuery(text="programming language", top_k=5))
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_statistics(self):
        store = InMemoryKnowledgeStore()
        manager = KnowledgeManager(store=store)
        await manager.initialize()

        await manager.ingest(content="Doc 1 content", title="Doc1", source="a.md")
        await manager.ingest(content="Doc 2 content", title="Doc2", source="b.md")

        stats = await manager.statistics()
        assert stats.total_items == 2
        assert stats.total_chunks >= 2  # At least one chunk per doc

    @pytest.mark.asyncio
    async def test_delete(self):
        store = InMemoryKnowledgeStore()
        manager = KnowledgeManager(store=store)
        await manager.initialize()

        item, _ = await manager.ingest(content="Test", title="Test", source="test")
        assert await manager.get(item.id) is not None
        assert await manager.delete(item.id)
        assert await manager.get(item.id) is None

    @pytest.mark.asyncio
    async def test_refresh(self):
        store = InMemoryKnowledgeStore()
        manager = KnowledgeManager(store=store)
        await manager.initialize()
        await manager.refresh()  # Should not throw

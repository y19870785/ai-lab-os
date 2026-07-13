"""Knowledge Pipeline Integration Tests.

Validates ingestion, chunking, and retrieval with Mock Providers.
"""

import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.providers.embedding.mock import MockEmbeddingProvider
from core.providers.vector.mock import MockVectorProvider
from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.retrieval import VectorRetriever, KeywordRetriever
from core.knowledge.ranking import KnowledgeRanker
from core.knowledge.chunking import get_chunker
from core.knowledge.models import KnowledgeItem, KnowledgeQuery, SourceType, KnowledgeType


class TestKnowledgePipeline:

    async def test_ingest_plaintext(self):
        pipe = IngestionPipeline()
        content = "AI-Lab is a personal AI operating system."
        item, chunks = await pipe.ingest(
            content=content, title="AI-Lab Intro", source="test.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
            author="test", tags=["ai-lab"],
        )
        assert isinstance(item, KnowledgeItem)
        assert item.title == "AI-Lab Intro"
        assert len(chunks) > 0

    async def test_ingest_and_keyword_search(self):
        pipe = IngestionPipeline()
        kw = KeywordRetriever()
        content = "Python is used in data science, web dev, and AI research."
        item, chunks = await pipe.ingest(
            content=content, title="Python", source="python.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        kw.index(item)
        results = kw.search("data science", top_k=3)
        assert len(results) > 0

    async def test_vector_retrieval(self):
        emb = MockEmbeddingProvider()
        vec = MockVectorProvider()
        await emb.initialize()
        await vec.initialize()
        pipe = IngestionPipeline(embedding_provider=emb, vector_provider=vec)
        vr = VectorRetriever(embedding_provider=emb, vector_provider=vec)
        content = "Machine learning is a subset of AI dealing with neural networks."
        item, chunks = await pipe.ingest(
            content=content, title="ML", source="ml.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        for chunk in chunks:
            await vr.index_chunk(chunk.chunk_id, chunk.content)
        results = await vr.search("neural networks", top_k=3)
        assert len(results) >= 1
        await emb.shutdown()
        await vec.shutdown()

    async def test_ranking(self):
        pipe = IngestionPipeline()
        kw = KeywordRetriever()
        content = "AI agents autonomously perform tasks using tools and memory."
        item, chunks = await pipe.ingest(
            content=content, title="Agents", source="a.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        kw.index(item)
        raw = kw.search("AI agents tools", top_k=5)
        items = [item for _ in raw]
        vs = {item.id: s for item_id, s in raw}
        ks = {item.id: s for item_id, s in raw}
        ranker = KnowledgeRanker()
        ranked = ranker.rank(items, vector_scores=vs, keyword_scores=ks)
        assert len(ranked) > 0
        assert ranked[0].score >= ranked[-1].score

    async def test_chunking_strategies(self):
        content = "# A\nContent A.\n\n# B\nContent B."
        for name in ["fixed_length", "sentence", "paragraph", "markdown", "recursive"]:
            chunker = get_chunker(name)
            pipe = IngestionPipeline(chunker=chunker)
            item, chunks = await pipe.ingest(
                content=content, title="T", source="t.md",
                source_type=SourceType.MARKDOWN, knowledge_type=KnowledgeType.DOCUMENT,
            )
            assert len(chunks) > 0, f"{name} chunker empty"

    async def test_metadata_extraction(self):
        pipe = IngestionPipeline()
        content = "# Test\nAuthor: Team\n\nContent here."
        item, chunks = await pipe.ingest(
            content=content, title="Meta", source="m.md",
            source_type=SourceType.MARKDOWN, knowledge_type=KnowledgeType.DOCUMENT,
            author="AI-Lab", language="en", tags=["test"],
        )
        assert item.author == "AI-Lab"
        assert "test" in item.tags

    async def test_empty_content(self):
        pipe = IngestionPipeline()
        item, chunks = await pipe.ingest(content="", title="E", source="e.txt")
        assert isinstance(item, KnowledgeItem)

    async def test_large_document(self):
        pipe = IngestionPipeline()
        kw = KeywordRetriever()
        sentences = [f"Sentence {i} about AI topics." for i in range(100)]
        content = " ".join(sentences)
        item, chunks = await pipe.ingest(
            content=content, title="Large", source="l.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        assert len(chunks) > 0
        kw.index(item)
        results = kw.search("Sentence 50", top_k=3)
        assert len(results) > 0

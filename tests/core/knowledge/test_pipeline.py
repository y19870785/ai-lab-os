"""Tests for ingestion pipeline."""
import pytest
from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.chunking import get_chunker
from core.knowledge.models import SourceType, KnowledgeType


class TestIngestionPipeline:
    @pytest.mark.asyncio
    async def test_basic_ingestion(self):
        pipeline = IngestionPipeline(chunker=get_chunker("fixed_length", chunk_size=100, overlap=20))
        item, chunks = await pipeline.ingest(
            content="Hello world. " * 50,
            title="Test Document",
            source="test.txt",
            source_type=SourceType.PLAINTEXT,
        )
        assert item.title == "Test Document"
        assert item.source == "test.txt"
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_metadata_extraction(self):
        pipeline = IngestionPipeline(chunker=get_chunker("recursive"))
        item, chunks = await pipeline.ingest(
            content="这是一段#Python测试文本，参考 https://example.com",
            title="Test",
            source="test",
        )
        assert item.language == "zh"
        assert "Python" in item.tags
        assert "https://example.com" in item.references

    @pytest.mark.asyncio
    async def test_with_embedding_and_vector(self):
        from core.providers.embedding.mock import MockEmbeddingProvider
        from core.providers.vector.mock import MockVectorProvider

        emb = MockEmbeddingProvider()
        await emb.initialize()
        vec = MockVectorProvider()
        await vec.initialize()

        pipeline = IngestionPipeline(
            chunker=get_chunker("fixed_length", chunk_size=200),
            embedding_provider=emb,
            vector_provider=vec,
        )
        item, chunks = await pipeline.ingest(
            content="Hello world. " * 30,
            title="With Embedding",
            source="test",
        )
        assert len(chunks) >= 1
        # Verify chunks were indexed in vector store
        from core.providers.vector import VectorSearchQuery
        results = await vec.search("knowledge", VectorSearchQuery(
            vector=await emb.embed_query("hello"),
            top_k=5,
        ))
        assert len(results) >= 1

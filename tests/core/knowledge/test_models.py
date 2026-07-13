"""Tests for Knowledge Layer models."""
import pytest
from core.knowledge.models import (
    KnowledgeItem, DocumentChunk, KnowledgeQuery, KnowledgeResult,
    KnowledgeType, SourceType, KnowledgeStats,
)


class TestKnowledgeModels:
    def test_knowledge_item_defaults(self):
        item = KnowledgeItem(title="Test", content="Hello world")
        assert item.id
        assert len(item.id) == 32
        assert item.title == "Test"
        assert item.content == "Hello world"
        assert item.confidence == 0.5
        assert item.importance == 0.5
        assert item.version == 1
        assert item.language == "zh"
        assert item.tags == []

    def test_document_chunk_defaults(self):
        chunk = DocumentChunk(content="hello", document_id="doc1", index=0)
        assert chunk.chunk_id
        assert chunk.document_id == "doc1"
        assert chunk.index == 0
        assert chunk.token_count == 0
        assert chunk.embedding_id is None

    def test_knowledge_query_defaults(self):
        q = KnowledgeQuery(text="test")
        assert q.top_k == 10
        assert q.offset == 0
        assert q.rerank is True
        assert q.min_score == 0.0

    def test_knowledge_type_values(self):
        assert KnowledgeType.DOCUMENT.value == "document"
        assert KnowledgeType.ENTITY.value == "entity"

    def test_source_type_values(self):
        assert SourceType.MARKDOWN.value == "markdown"
        assert SourceType.PDF.value == "pdf"
        assert SourceType.PLAINTEXT.value == "plaintext"

    def test_knowledge_stats_defaults(self):
        stats = KnowledgeStats()
        assert stats.total_items == 0
        assert stats.total_chunks == 0
        assert stats.by_type == {}

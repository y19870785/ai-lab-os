"""Tests for all chunking strategies."""
import pytest
from core.knowledge.chunking import (
    get_chunker, FixedLengthChunker, SentenceChunker,
    ParagraphChunker, MarkdownChunker, RecursiveChunker, TokenWindowChunker,
)

SAMPLE_TEXT = "Hello world. This is a test. Another sentence here.\n\nNew paragraph starts now with more content."


class TestFixedLength:
    def test_basic_chunking(self):
        c = FixedLengthChunker(chunk_size=20, overlap=0)
        chunks = c.chunk("abcdefghijklmnopqrstuvwxyz", "doc1")
        assert len(chunks) == 2  # 26 chars -> 20 + 6
        assert chunks[0].index == 0
        assert chunks[1].index == 1
        assert chunks[0].document_id == "doc1"

    def test_overlap(self):
        c = FixedLengthChunker(chunk_size=10, overlap=3)
        chunks = c.chunk("1234567890123456", "doc1")
        # 16 chars: 0-10, then 7-16
        assert len(chunks) >= 1
        assert chunks[0].content.startswith("1234567890")

    def test_empty(self):
        c = FixedLengthChunker()
        assert c.chunk("", "doc1") == []


class TestSentence:
    def test_sentence_chunking(self):
        c = SentenceChunker(chunk_size=100)
        chunks = c.chunk("Hello world. This is another sentence. And more stuff.", "doc1")
        assert len(chunks) >= 1

    def test_chinese(self):
        c = SentenceChunker(chunk_size=100)
        chunks = c.chunk("你好世界。这是测试。还有更多内容。", "doc1")
        assert len(chunks) >= 1


class TestParagraph:
    def test_paragraph_chunking(self):
        c = ParagraphChunker(chunk_size=200)
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = c.chunk(text, "doc1")
        assert len(chunks) >= 1

    def test_single_paragraph(self):
        c = ParagraphChunker()
        chunks = c.chunk("Just one paragraph.", "doc1")
        assert len(chunks) == 1


class TestMarkdown:
    def test_header_chunking(self):
        c = MarkdownChunker(chunk_size=200)
        text = "# Title\nSome content.\n\n## Section 1\nMore content.\n\n## Section 2\nEven more."
        chunks = c.chunk(text, "doc1")
        assert len(chunks) >= 2  # Title + at least one section


class TestRecursive:
    def test_recursive_chunking(self):
        c = RecursiveChunker(chunk_size=50, overlap=10)
        chunks = c.chunk(SAMPLE_TEXT * 10, "doc1")
        assert len(chunks) >= 1
        for chunk in chunks:
            assert len(chunk.content) <= 50 + 10  # Max chunk_size + overlap


class TestTokenWindow:
    def test_sliding_window(self):
        c = TokenWindowChunker(window_size=20, overlap=5)
        text = "A" * 50
        chunks = c.chunk(text, "doc1")
        assert len(chunks) >= 2


class TestGetChunker:
    def test_factory(self):
        for name in ["fixed_length", "sentence", "paragraph", "markdown", "recursive", "token_window"]:
            c = get_chunker(name)
            assert c.name == name

    def test_unknown_strategy(self):
        with pytest.raises(ValueError, match="Unknown"):
            get_chunker("nonexistent")

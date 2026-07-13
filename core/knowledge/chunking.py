"""Document chunking strategies.

Supported strategies:
- fixed_length  : split at every N characters
- sentence      : split at sentence boundaries
- paragraph     : split at double newlines
- markdown      : split at markdown headers (##)
- recursive     : try separators in order, fall back to fixed
- token_window  : sliding window of N characters with overlap

All strategies implement ChunkStrategy protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from core.knowledge.models import DocumentChunk


class ChunkStrategy(ABC):
    """Abstract chunking strategy."""

    @abstractmethod
    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        """Split text into chunks."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Strategy identifier."""
        ...


class FixedLengthChunker(ChunkStrategy):
    """Split at every N characters."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "fixed_length"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            content = text[start:end]
            chunks.append(DocumentChunk(
                document_id=document_id,
                index=idx,
                content=content,
                token_count=len(content),
            ))
            idx += 1
            start = end - self._overlap if end < len(text) else end
        return chunks


class SentenceChunker(ChunkStrategy):
    """Split at sentence boundaries (。.!?\n)."""

    def __init__(self, chunk_size: int = 512, overlap: int = 0) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "sentence"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        import re
        sentences = re.split(r'(?<=[。.!?！？\n])\s*', text)
        sentences = [s for s in sentences if s.strip()]

        chunks = []
        current = ""
        idx = 0
        for sent in sentences:
            if len(current) + len(sent) > self._chunk_size and current:
                chunks.append(DocumentChunk(
                    document_id=document_id, index=idx,
                    content=current.strip(), token_count=len(current),
                ))
                idx += 1
                current = sent
            else:
                current += " " + sent if current else sent
        if current.strip():
            chunks.append(DocumentChunk(
                document_id=document_id, index=idx,
                content=current.strip(), token_count=len(current),
            ))
        return chunks


class ParagraphChunker(ChunkStrategy):
    """Split at double-newline boundaries."""

    def __init__(self, chunk_size: int = 1024, overlap: int = 0) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "paragraph"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        paragraphs = text.split("\n\n")
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        chunks = []
        current = ""
        idx = 0
        for para in paragraphs:
            if len(current) + len(para) > self._chunk_size and current:
                chunks.append(DocumentChunk(
                    document_id=document_id, index=idx,
                    content=current.strip(), token_count=len(current),
                ))
                idx += 1
                current = para
            else:
                current += "\n\n" + para if current else para
        if current.strip():
            chunks.append(DocumentChunk(
                document_id=document_id, index=idx,
                content=current.strip(), token_count=len(current),
            ))
        return chunks


class MarkdownChunker(ChunkStrategy):
    """Split at markdown headers (##)."""

    def __init__(self, chunk_size: int = 1024) -> None:
        self._chunk_size = chunk_size

    @property
    def name(self) -> str:
        return "markdown"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        import re
        # Split by markdown headers
        sections = re.split(r'(?=^#{1,6}\s)', text, flags=re.MULTILINE)
        sections = [s.strip() for s in sections if s.strip()]

        chunks = []
        for idx, section in enumerate(sections):
            # If section is too large, sub-split
            if len(section) <= self._chunk_size:
                chunks.append(DocumentChunk(
                    document_id=document_id, index=idx,
                    content=section, token_count=len(section),
                ))
            else:
                sub = FixedLengthChunker(self._chunk_size)
                sub_chunks = sub.chunk(section, document_id)
                for sc in sub_chunks:
                    sc.index = len(chunks)
                    chunks.append(sc)
        return chunks


class RecursiveChunker(ChunkStrategy):
    """Try separators in order: \n\n → \n → . → '' (character)."""

    def __init__(self, chunk_size: int = 512, overlap: int = 50,
                 separators: list[str] | None = None) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap
        self._separators = separators or ["\n\n", "\n", ". ", "。", " ", ""]

    @property
    def name(self) -> str:
        return "recursive"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        return self._split(text, document_id, self._separators)

    def _split(self, text: str, doc_id: str, separators: list[str]) -> list[DocumentChunk]:
        sep = separators[0]
        next_seps = separators[1:]

        if sep == "" or not next_seps:
            # Final fallback: fixed length
            return FixedLengthChunker(self._chunk_size, self._overlap).chunk(text, doc_id)

        parts = text.split(sep)
        chunks = []
        current = ""
        idx = 0

        for part in parts:
            candidate = current + sep + part if current else part
            if len(candidate) > self._chunk_size:
                # Current batch is full; recursively split it
                if current:
                    sub = self._split(current, doc_id, next_seps)
                    for sc in sub:
                        sc.index = len(chunks)
                        chunks.append(sc)
                current = part
            else:
                current = candidate

        if current:
            sub = self._split(current, doc_id, next_seps)
            for sc in sub:
                sc.index = len(chunks)
                chunks.append(sc)

        return chunks


class TokenWindowChunker(ChunkStrategy):
    """Sliding window of N characters with overlap."""

    def __init__(self, window_size: int = 256, overlap: int = 64) -> None:
        self._window_size = window_size
        self._overlap = overlap

    @property
    def name(self) -> str:
        return "token_window"

    def chunk(self, text: str, document_id: str, **kwargs: Any) -> list[DocumentChunk]:
        chunks = []
        start = 0
        idx = 0
        while start < len(text):
            end = min(start + self._window_size, len(text))
            content = text[start:end]
            chunks.append(DocumentChunk(
                document_id=document_id, index=idx,
                content=content, token_count=len(content),
            ))
            idx += 1
            if end >= len(text):
                break
            start = end - self._overlap
        return chunks


# ── Chunker factory ──

def get_chunker(strategy: str, **kwargs: Any) -> ChunkStrategy:
    """Factory for chunking strategies.

    Args:
        strategy: "fixed_length" | "sentence" | "paragraph" | "markdown" | "recursive" | "token_window"
        **kwargs: passed to chunker constructor

    Returns:
        ChunkStrategy instance.
    """
    chunkers: dict[str, type[ChunkStrategy]] = {
        "fixed_length": FixedLengthChunker,
        "sentence": SentenceChunker,
        "paragraph": ParagraphChunker,
        "markdown": MarkdownChunker,
        "recursive": RecursiveChunker,
        "token_window": TokenWindowChunker,
    }
    cls = chunkers.get(strategy)
    if cls is None:
        raise ValueError(f"Unknown chunking strategy: {strategy}. Choose from: {list(chunkers.keys())}")
    return cls(**kwargs)

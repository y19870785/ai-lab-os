"""Chunk 策略抽象和内置实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from knowledge.models.document import Chunk, DocumentMetadata


class ChunkStrategy(ABC):
    """文本切割策略抽象。"""

    @abstractmethod
    async def chunk(self, text: str, metadata: DocumentMetadata) -> list[Chunk]:
        """将文本切割为知识块。"""
        ...

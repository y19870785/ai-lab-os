"""Markdown 结构切割器。按标题层级切割，保留文档结构。"""
# 骨架文件

from knowledge.chunking.protocol import ChunkStrategy
from knowledge.models.document import Chunk, DocumentMetadata


class MarkdownChunker(ChunkStrategy):
    """Markdown 结构切割器。按标题 (# ## ###) 层级切割。"""

    async def chunk(self, text: str, metadata: DocumentMetadata) -> list[Chunk]:
        """TODO: Phase 1.4b 实现。"""
        return []

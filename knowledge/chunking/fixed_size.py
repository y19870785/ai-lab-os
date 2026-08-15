"""固定大小切割器。按字符/token 数固定切割。"""
# 骨架文件

from knowledge.chunking.protocol import ChunkStrategy
from knowledge.models.document import Chunk, DocumentMetadata


class FixedSizeChunker(ChunkStrategy):
    """固定大小切割器。"""

    async def chunk(self, text: str, metadata: DocumentMetadata) -> list[Chunk]:
        """TODO: Phase 1.4b 实现。"""
        return []

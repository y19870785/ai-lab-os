"""递归分割器。按分隔符列表逐层递归切割。"""
# 骨架文件，Phase 1.4b 实现

from knowledge.chunking.protocol import ChunkStrategy
from knowledge.models.document import Chunk, DocumentMetadata


class RecursiveChunker(ChunkStrategy):
    """递归分割器。按分隔符优先级逐层切割。"""

    async def chunk(self, text: str, metadata: DocumentMetadata) -> list[Chunk]:
        """TODO: Phase 1.4b 实现。"""
        return []

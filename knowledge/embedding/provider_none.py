"""降级 Embedding 实现。不做向量化，返回空向量。当无 embedding provider 可用时使用。"""
# 骨架文件

from knowledge.embedding.protocol import EmbeddingProvider


class NoneEmbeddingProvider(EmbeddingProvider):
    """降级实现。不做 embedding，所有文本返回空列表。"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return []

    @property
    def dimensions(self) -> int:
        return 0

    @property
    def model_name(self) -> str:
        return "none"

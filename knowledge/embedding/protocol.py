"""Embedding Provider 抽象。与 Memory Layer 的 Embedding 接口对齐。"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Embedding 提供者抽象。负责将文本转化为向量。"""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """将一批文本转化为向量。"""
        ...

    @abstractmethod
    async def embed_query(self, query: str) -> list[float]:
        """将查询文本转化为向量（可针对查询优化）。"""
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """返回向量维度。"""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回模型名称。"""
        ...

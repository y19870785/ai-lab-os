"""存储层抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from knowledge.models import KnowledgeType
from knowledge.models.document import Chunk


class KnowledgeQuery(BaseModel):
    """知识查询参数。"""
    knowledge_type: KnowledgeType | None = None
    filters: dict[str, Any] = {}
    limit: int = 100
    offset: int = 0


class KnowledgeStore(ABC):
    """知识存储抽象。负责结构化知识条目的持久化。"""

    @abstractmethod
    async def save(self, knowledge_type: KnowledgeType, data: dict) -> str: ...
    @abstractmethod
    async def get(self, knowledge_type: KnowledgeType, id: str) -> dict | None: ...
    @abstractmethod
    async def delete(self, knowledge_type: KnowledgeType, id: str) -> bool: ...
    @abstractmethod
    async def query(self, query: KnowledgeQuery) -> list[dict]: ...


class VectorStore(ABC):
    """向量存储抽象。负责向量索引和语义检索。"""

    @abstractmethod
    async def upsert(self, collection: str, id: str, vector: list[float], payload: dict) -> None: ...
    @abstractmethod
    async def search(self, collection: str, vector: list[float], top_k: int, filters: dict | None = None) -> list[dict]: ...
    @abstractmethod
    async def delete(self, collection: str, id: str) -> bool: ...
    @abstractmethod
    async def count(self, collection: str) -> int: ...


class GraphStore(ABC):
    """图存储抽象。负责实体关系和图遍历。"""

    @abstractmethod
    async def add_entity(self, entity_id: str, entity_type: str, properties: dict) -> None: ...
    @abstractmethod
    async def add_relation(self, source_id: str, target_id: str, relation_type: str, properties: dict) -> None: ...
    @abstractmethod
    async def traverse(self, entity_id: str, relation_types: list[str] | None, depth: int) -> list[dict]: ...

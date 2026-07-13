"""实体知识和关系知识数据模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from knowledge.models import AccessLevel


class EntityType(str, Enum):
    """实体类型。"""
    PERSON = "person"
    ORGANIZATION = "organization"
    CONCEPT = "concept"
    PRODUCT = "product"
    TERM = "term"
    LOCATION = "location"
    EVENT = "event"
    CUSTOM = "custom"


class EntityKnowledge(BaseModel):
    """实体知识。知识图谱的节点。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str
    type: EntityType = EntityType.CUSTOM
    aliases: list[str] = []
    attributes: dict[str, Any] = {}
    description: str = ""
    embedding: list[float] | None = None
    sources: list[str] = []

    access_level: AccessLevel = AccessLevel.PRIVATE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class RelationKnowledge(BaseModel):
    """关系知识。知识图谱的边。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    relation_label: str = ""
    weight: float = 1.0
    attributes: dict[str, Any] = {}
    confidence: float = 1.0

    sources: list[str] = []
    access_level: AccessLevel = AccessLevel.PRIVATE
    created_at: datetime = Field(default_factory=datetime.now)

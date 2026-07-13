"""Knowledge Layer 数据模型 —— 共用类型。"""

from __future__ import annotations

from enum import Enum


class KnowledgeType(str, Enum):
    """知识类型。"""
    DOCUMENT = "document"
    ENTITY = "entity"
    RELATION = "relation"
    EXPERIENCE = "experience"
    DECISION = "decision"


class AccessLevel(str, Enum):
    """知识访问级别。"""
    PUBLIC = "public"
    TEAM = "team"
    PRIVATE = "private"
    RESTRICTED = "restricted"


class SourceType(str, Enum):
    """知识来源类型。"""
    PDF = "pdf"
    MARKDOWN = "markdown"
    HTML = "html"
    CSV = "csv"
    JSON = "json"
    API = "api"
    TEXT = "text"


class ContentType(str, Enum):
    """内容结构化程度。"""
    STRUCTURED = "structured"
    SEMI_STRUCTURED = "semi_structured"
    UNSTRUCTURED = "unstructured"

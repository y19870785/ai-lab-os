"""文档知识数据模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from knowledge.models import AccessLevel, ContentType, SourceType


class DocumentMetadata(BaseModel):
    """文档级元数据。"""
    author: str | None = None
    tags: list[str] = []
    language: str = "zh"
    source_url: str | None = None
    file_size: int = 0
    page_count: int | None = None
    custom: dict[str, Any] = {}


class Chunk(BaseModel):
    """知识块——检索和引用的原子单位。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    document_id: str
    content: str
    chunk_index: int = 0
    heading: str | None = None
    start_char: int = 0
    end_char: int = 0
    page_number: int | None = None
    tokens: int = 0

    embedding: list[float] | None = None
    entities: list[str] = []


class DocumentKnowledge(BaseModel):
    """文档知识。知识的原子单位——一篇文档/一个页面。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str
    source: str = ""
    source_type: SourceType = SourceType.TEXT
    content_type: ContentType = ContentType.UNSTRUCTURED

    raw_content: str = ""
    metadata: DocumentMetadata = DocumentMetadata()
    chunks: list[Chunk] = []
    summary: str | None = None
    embedding: list[float] | None = None

    version: int = 1
    access_level: AccessLevel = AccessLevel.PRIVATE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

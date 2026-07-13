"""Knowledge Layer data models.

Core types:
- KnowledgeItem: the central knowledge record (doc, entity, snippet, etc.)
- DocumentChunk: a piece of a larger document after chunking
- KnowledgeQuery: retrieval query specification
- KnowledgeResult: scored retrieval result
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeType(str, Enum):
    """Category of knowledge."""
    DOCUMENT = "document"
    ENTITY = "entity"
    RELATION = "relation"
    EXPERIENCE = "experience"
    DECISION = "decision"
    SNIPPET = "snippet"


class SourceType(str, Enum):
    """Where the knowledge came from."""
    MARKDOWN = "markdown"
    PDF = "pdf"
    HTML = "html"
    PLAINTEXT = "plaintext"
    CODE = "code"
    DATABASE = "database"
    API = "api"
    MANUAL = "manual"
    AGENT = "agent"
    WEBPAGE = "webpage"


class KnowledgeItem(BaseModel):
    """Central knowledge record.

    Every piece of ingested knowledge is represented as a KnowledgeItem.
    The content field stores the raw or processed text.
    """

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    title: str = ""
    source: str = ""                    # e.g. file path, URL, agent name
    source_type: SourceType = SourceType.PLAINTEXT
    knowledge_type: KnowledgeType = KnowledgeType.DOCUMENT
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding_id: str | None = None     # reference into VectorProvider
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    language: str = "zh"
    author: str = ""
    tags: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)  # IDs of related items
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class DocumentChunk(BaseModel):
    """A single chunk of a larger document."""

    chunk_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    document_id: str = ""               # parent KnowledgeItem.id
    index: int = 0                      # position in document
    content: str = ""
    token_count: int = 0
    embedding_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeQuery(BaseModel):
    """Retrieval query specification."""

    text: str = ""
    top_k: int = Field(default=10, ge=1)
    offset: int = Field(default=0, ge=0)
    filters: dict[str, Any] = Field(default_factory=dict)
    rerank: bool = True
    include_metadata: bool = True
    include_score: bool = True
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class KnowledgeResult(BaseModel):
    """Scored retrieval result."""

    item: KnowledgeItem
    score: float = 0.0
    distance: float | None = None
    rerank_score: float | None = None
    chunks: list[DocumentChunk] = Field(default_factory=list)


class KnowledgeStats(BaseModel):
    """Aggregated knowledge statistics."""

    total_items: int = 0
    total_chunks: int = 0
    by_type: dict[str, int] = Field(default_factory=dict)
    by_source: dict[str, int] = Field(default_factory=dict)
    avg_confidence: float = 0.0
    last_ingested: datetime | None = None

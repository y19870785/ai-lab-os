"""Memory Layer 数据模型。

定义核心数据类型：
- MemoryType: 记忆类型枚举
- MemoryItem: 通用记忆条目
- MemoryQuery: 检索查询（支持过滤/排序/分页）
- MemoryFilter: 轻量计数过滤
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """记忆类型。"""
    SESSION = "session"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    DECISION = "decision"


class MemoryItem(BaseModel):
    """通用记忆条目。所有记忆类型的统一载体。

    content 字段按 memory_type 携带不同的结构化数据：
    - SESSION:  session_id, messages, context, agent_state
    - EPISODIC: session_id, agent_id, events, summary
    - SEMANTIC: entity_type, entity_name, properties 或 relation 数据
    - DECISION: agent_id, session_id, trigger, alternatives, reasoning_chain, chosen, outcome
    """

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    memory_type: MemoryType
    content: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)
    ttl: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryFilter(BaseModel):
    """轻量计数过滤条件。

    用于 MemoryStore.count(filter) 的简单过滤。
    复杂检索请使用 MemoryQuery。
    """

    memory_type: MemoryType | None = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    max_importance: float = Field(default=1.0, ge=0.0, le=1.0)
    time_after: datetime | None = None
    time_before: datetime | None = None


class MemoryQuery(BaseModel):
    """记忆检索查询。

    所有字段均为可选：空查询返回 all（受 top_k 限制）。
    所有 Store 必须完整支持 fields/top_k/offset/sort_by/sort_desc。
    """

    query_text: str | None = None
    query_embedding: list[float] | None = None
    memory_type: MemoryType | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    time_range: tuple[datetime, datetime] | None = None
    top_k: int = Field(default=10, ge=1)
    offset: int = Field(default=0, ge=0)
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)
    sort_by: str | None = None          # "importance" | "timestamp"
    sort_desc: bool = True               # True=降序, False=升序
"""事件数据模型。

定义 Event 和 Task 两个核心消息类型。
Event 用于 Pub-Sub 通信，Task 用于点对点任务分发。

事件类型约定：
    stock.price.changed
    agent.task.created
    agent.task.completed
    knowledge.updated
    memory.created
    memory.updated
    memory.deleted
    system.config.changed

使用方式：
    from core.bus import Event, EventType, Task

    event = Event(
        event_type="memory.created",
        source="memory.episodic",
        payload={"memory_id": "xxx", "memory_type": "episodic"},
    )
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class Event(BaseModel):
    """事件数据模型。

    用于 Event Bus 的 Pub-Sub 通信。
    所有字段通用化，不绑定任何业务语义。
    """

    event_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="全局唯一事件 ID",
    )
    event_type: str = Field(
        ...,
        description="事件类型标识，如 stock.price.changed",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="事件产生时间戳",
    )
    source: str = Field(
        ...,
        description="事件来源，如 agent.analyst, memory.episodic",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="事件载荷，自由结构",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="事件元数据，trace_id, agent_id 等上下文",
    )


class Task(BaseModel):
    """任务数据模型。

    用于 Task Queue 的点对点分发。
    """

    task_id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="全局唯一任务 ID",
    )
    queue: str = Field(
        ...,
        description="目标队列名，如 agent.analyst.run",
    )
    payload: dict[str, Any] = Field(
        ...,
        description="任务载荷",
    )
    priority: int = Field(
        0,
        ge=0, le=10,
        description="优先级，0=最低，10=最高",
    )
    max_retries: int = Field(
        3,
        ge=0,
        description="最大重试次数",
    )
    timeout: int = Field(
        60,
        ge=1,
        description="任务超时时间（秒）",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="任务创建时间",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="任务元数据，trace_id, agent_id 等上下文",
    )

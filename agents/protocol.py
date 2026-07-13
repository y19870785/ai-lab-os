"""Agent 协议。定义 Agent 间标准化通信语义，基于 Core Message Bus 构建。

Agent Protocol 在 Message Bus 之上增加 Agent 间通信的语义层。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentMessageType(str, Enum):
    """Agent 间消息类型。"""
    # 任务委托
    DELEGATE = "delegate"
    DELEGATE_RESULT = "delegate_result"

    # 信息查询
    QUERY = "query"
    QUERY_RESULT = "query_result"

    # 通知
    NOTIFY = "notify"
    BROADCAST = "broadcast"

    # 协调
    COORDINATE = "coordinate"
    COORDINATE_ACK = "coordinate_ack"


class AgentMessage(BaseModel):
    """Agent 间通信消息。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    sender_id: str
    target_id: str | None = None
    conversation_id: str = ""
    message_type: AgentMessageType
    payload: dict[str, Any] = {}
    priority: int = 0
    ttl: int = 300
    reply_to: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class AgentProtocol(ABC):
    """Agent 间通信协议。基于 Message Bus 的语义层。"""

    @abstractmethod
    async def send_message(self, message: AgentMessage) -> str:
        """发送一条 Agent 消息。返回消息 ID。"""
        ...

    @abstractmethod
    async def register_handler(self, agent_id: str, handler) -> None:
        """注册消息处理器。"""
        ...

    @abstractmethod
    async def delegate(self, target_id: str, task: "agents.context.AgentTask") -> str:  # noqa: F821
        """委托一个任务给另一个 Agent。返回 conversation_id。"""
        ...

    @abstractmethod
    async def query(self, target_id: str, query: str, context: dict[str, Any] | None = None) -> Any:
        """向另一个 Agent 查询信息。等待结果。"""
        ...

    @abstractmethod
    async def notify(self, target_id: str, event: str, data: dict[str, Any]) -> None:
        """发送单向通知。"""
        ...

    @abstractmethod
    async def broadcast(self, message: str, data: dict[str, Any]) -> None:
        """广播消息给所有 Agent。"""
        ...

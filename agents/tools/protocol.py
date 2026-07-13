"""工具定义与接口协议。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Protocol

from pydantic import BaseModel, Field


class ExecutionType(str, Enum):
    """工具执行模式。"""
    SYNC = "sync"
    ASYNC = "async"
    STREAMING = "streaming"


class ToolCallStatus(str, Enum):
    """工具调用状态。"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JsonSchema(BaseModel):
    """JSON Schema 定义工具参数和返回值结构。"""
    type: str = "object"
    properties: dict[str, Any] = {}
    required: list[str] = []


class Tool(BaseModel):
    """工具定义。"""
    name: str
    description: str
    version: str = "1.0.0"
    parameters: JsonSchema = JsonSchema()
    returns: JsonSchema = JsonSchema()
    timeout: int = 30
    execution_type: ExecutionType = ExecutionType.SYNC
    requires_approval: bool = False


class ToolCall(BaseModel):
    """工具调用记录。"""
    call_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    tool_name: str
    arguments: dict[str, Any] = {}
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Any = None
    error: str | None = None
    started_at: datetime = Field(default_factory=datetime.now)
    completed_at: datetime | None = None
    token_cost: int = 0


class ToolCallResult(BaseModel):
    """工具调用结果。"""
    call_id: str
    success: bool
    data: Any = None
    error: str | None = None
    elapsed_ms: int = 0


class ToolHandler(Protocol):
    """工具执行器类型签名。"""

    async def __call__(self, arguments: dict[str, Any]) -> Any:
        ...


class ToolFilter(BaseModel):
    """工具查询过滤器。"""
    name_pattern: str | None = None
    execution_type: ExecutionType | None = None
    requires_approval: bool | None = None

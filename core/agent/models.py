"""Agent 数据模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    """Agent 运行时状态。"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class AgentSpec(BaseModel):
    """Agent 定义规范。描述 Agent 的类型和能力。"""
    name: str
    version: str
    description: str = ""
    capabilities: list[str] = []
    config_schema: dict[str, Any] = {}
    timeout: int = 60


class AgentInstance(BaseModel):
    """Agent 运行时实例。"""
    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    spec: AgentSpec
    status: AgentStatus = AgentStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.now)
    last_heartbeat: datetime | None = None
    metadata: dict[str, Any] = {}


class AgentFilter(BaseModel):
    """Agent 查询过滤器。"""
    status: AgentStatus | None = None
    capability: str | None = None
    name_pattern: str | None = None

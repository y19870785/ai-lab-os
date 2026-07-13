"""Application Foundation Models —— 业务应用基础数据模型。"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field

from core.workspace.models import WorkspaceKey


class ApplicationStatus(str, Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ApplicationInfo(BaseModel):
    """应用元数据。"""
    application_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    entrypoint: str = ""
    status: ApplicationStatus = ApplicationStatus.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationManifest(BaseModel):
    """应用清单 —— 声明应用的依赖和配置。"""
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    entrypoint: str = ""
    required_agents: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    required_providers: list[str] = Field(default_factory=list)
    required_permissions: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    health_checks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationContext(BaseModel):
    """应用执行上下文 —— 统一携带所有隔离信息。

    这是 Application 层向下传递的唯一上下文载体。
    """
    application_id: str = ""
    workspace_key: WorkspaceKey = Field(default_factory=WorkspaceKey)
    # 别名（便捷访问）
    @property
    def tenant_id(self): return self.workspace_key.tenant_id
    @property
    def workspace_id(self): return self.workspace_key.workspace_id
    @property
    def user_id(self): return self.workspace_key.user_id
    @property
    def session_id(self): return self.workspace_key.session_id
    @property
    def trace_id(self): return self.workspace_key.trace_id

    environment: str = "dev"
    permissions: set[str] = Field(default_factory=set)
    variables: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationRequest(BaseModel):
    """应用请求 —— 从 API / CLI 进入 Application Runtime 的请求。"""
    application_name: str = ""
    user_input: str = ""
    workspace_key: WorkspaceKey = Field(default_factory=WorkspaceKey)
    mode: str = "sync"  # sync | async
    stream: bool = False
    timeout: int = 300
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApplicationResponse(BaseModel):
    """应用响应。"""
    application_id: str = ""
    answer: str = ""
    status: str = "ok"  # ok | error | partial
    citations: list[str] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    latency_ms: float = 0.0
    trace_id: str = ""
    mode: str = "mock"  # mock | real
    error: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

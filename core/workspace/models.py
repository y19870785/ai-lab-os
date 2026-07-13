"""Workspace/Tenant Models —— 多租户基础隔离模型。

定义 Workspace、Tenant、UserContext、Environment、Namespace。
当前阶段只实现逻辑隔离，不实现 SaaS 计费或复杂组织结构。
"""

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Environment(str, Enum):
    """运行环境。"""
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class WorkspaceStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Permission(str, Enum):
    """基础权限类型。"""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"
    NONE = "none"


# ---- 核心隔离模型 ----

class Tenant(BaseModel):
    """租户 —— 最高级隔离单位。"""
    tenant_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    name: str = ""
    description: str = ""
    environment: Environment = Environment.DEV
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Workspace(BaseModel):
    """工作空间 —— Tenant 下的隔离单元。

    一个 Tenant 可以有多个 Workspace。
    所有 Memory / Knowledge / Task / Workflow / Agent 操作都必须携带 workspace_id。
    """
    workspace_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    tenant_id: str = ""
    name: str = ""
    description: str = ""
    namespace: str = "default"  # 逻辑命名空间
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    environment: Environment = Environment.DEV
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class UserContext(BaseModel):
    """用户上下文 —— 当前操作者信息。"""
    user_id: str = ""
    tenant_id: str = ""
    workspace_id: str = ""
    roles: list[str] = Field(default_factory=list)
    permissions: list[Permission] = Field(default_factory=list)
    session_id: str = ""
    trace_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def has_permission(self, perm: Permission) -> bool:
        return perm in self.permissions or Permission.ADMIN in self.permissions


class Namespace(BaseModel):
    """逻辑命名空间 —— Workspace 内的进一步隔离。"""
    namespace_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)
    workspace_id: str = ""
    name: str = "default"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---- Workspace 上下文键 ----

class WorkspaceKey(BaseModel):
    """携带隔离信息的统一上下文键。

    所有底层调用（Memory / Knowledge / Task 等）都应该能通过
    这个 key 确定数据归属，防止跨 Workspace 数据污染。
    """
    tenant_id: str = ""
    workspace_id: str = ""
    namespace: str = "default"
    user_id: str = ""
    session_id: str = ""
    trace_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex)

    def to_filter(self) -> dict[str, str]:
        """生成用于数据过滤的 dict。"""
        return {
            "tenant_id": self.tenant_id,
            "workspace_id": self.workspace_id,
            "namespace": self.namespace,
        }

    def to_metadata(self) -> dict[str, str]:
        """生成用于写入数据 metadata 的 dict。"""
        return self.to_filter()

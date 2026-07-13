"""身份管理数据模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, Enum):
    """用户角色。"""
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"


class Permission(str, Enum):
    """权限标识。"""
    AGENT_RUN = "agent.run"
    AGENT_MANAGE = "agent.manage"
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    KNOWLEDGE_READ = "knowledge.read"
    KNOWLEDGE_WRITE = "knowledge.write"
    SYSTEM_CONFIG = "system.config"


class Credentials(BaseModel):
    """认证凭据。支持 API Key 和用户名密码。"""
    type: str = "api_key"           # "api_key" | "password"
    api_key: str | None = None
    username: str | None = None
    password: str | None = None


class User(BaseModel):
    """用户模型。"""
    id: str
    username: str
    role: Role = Role.USER
    permissions: list[Permission] = []
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)


class Session(BaseModel):
    """会话模型。"""
    id: str
    user_id: str
    token: str
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    is_active: bool = True

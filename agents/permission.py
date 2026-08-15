"""Agent 权限模型。定义 Agent 的能力边界和访问控制。

双层权限体系：
1. Agent 级权限：Agent 自身能调用哪些 Tools、访问哪些 Memory
2. 用户级权限：Agent 代用户执行时，受用户身份约束
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel

from core.memory.protocol import MemoryType


class AuditLevel(str, Enum):
    """审计级别。"""
    NONE = "none"                       # 不审计
    BASIC = "basic"                     # 只记录关键操作
    FULL = "full"                       # 记录所有操作


class AgentPermission(BaseModel):
    """Agent 权限声明。

    双层检查：Agent 能做什么 × 用户授权 Agent 做什么。
    """
    agent_id: str

    # Layer 1：Agent 自身能力边界
    allowed_tools: list[str] = ["*"]
    blocked_tools: list[str] = []
    allowed_memory_types: list[MemoryType] = [MemoryType.SESSION]

    # Layer 2：执行时的用户级约束
    require_user_approval: list[str] = []
    max_token_per_run: int = 100000
    allowed_hours: list[int] | None = None

    # 审计
    audit_level: AuditLevel = AuditLevel.BASIC
    metadata: dict[str, Any] = {}

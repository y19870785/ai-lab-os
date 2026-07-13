"""Agent 身份模型。定义 Agent 的身份声明、角色分类和能力声明。

身份模型是 Agent Layer 的核心——回答"Agent 是谁"的问题。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Agent 角色分类。

    角色定义了 Agent 的行为模式和职责边界。
    预定义角色作为系统内置模板，用户可通过 CUSTOM 扩展。
    """
    # ── 核心生产力角色 ──
    ANALYST = "analyst"
    SECRETARY = "secretary"
    RESEARCHER = "researcher"

    # ── 执行角色 ──
    ASSISTANT = "assistant"
    OPERATOR = "operator"
    WORKFLOW = "workflow"

    # ── 辅助角色 ──
    CRITIC = "critic"
    ORCHESTRATOR = "orchestrator"

    # ── 自定义扩展 ──
    CUSTOM = "custom"


class CapabilityType(str, Enum):
    """能力类型。"""
    TOOL = "tool"                       # 外部工具调用
    SKILL = "skill"                     # 内在分析/推理能力
    KNOWLEDGE = "knowledge"             # 特定知识域


class CapabilityDecl(BaseModel):
    """能力声明。描述 Agent 的一项具体能力。

    能力是声明式的——Agent 声明"我能做什么"，但不提供实现。
    实现由 ToolRegistry 根据 name 匹配。
    """
    name: str
    type: CapabilityType = CapabilityType.TOOL
    description: str = ""
    config: dict[str, Any] = {}


class AgentIdentity(BaseModel):
    """Agent 身份声明。

    描述一个 Agent 的核心身份特征。
    区别于 Core AgentSpec（技术描述），这里是"语义身份"。
    """
    agent_id: str
    name: str
    role: AgentRole = AgentRole.CUSTOM
    description: str = ""

    # 能力清单
    capabilities: list[CapabilityDecl] = []

    # 身份元数据
    version: str = "1.0.0"
    owner: str = "system"
    tags: list[str] = []
    avatar: str | None = None

    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

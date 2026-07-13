"""角色模板注册中心和预定义模板。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agents.identity import AgentRole, CapabilityDecl, CapabilityType


class RoleTemplate(BaseModel):
    """角色模板。包含预定义的身份、能力和记忆配置。"""
    role: AgentRole
    display_name: str
    description: str
    default_capabilities: list[CapabilityDecl] = []
    default_tags: list[str] = []
    config: dict[str, Any] = {}


# 预定义角色模板
BUILTIN_ROLES: dict[AgentRole, RoleTemplate] = {
    AgentRole.ANALYST: RoleTemplate(
        role=AgentRole.ANALYST,
        display_name="分析师",
        description="数据分析和报告生成。接收数据 → 分析 → 输出结构化报告。",
        default_capabilities=[
            CapabilityDecl(name="data_analysis", type=CapabilityType.SKILL, description="结构化数据分析"),
            CapabilityDecl(name="report_generation", type=CapabilityType.SKILL, description="报告生成"),
        ],
        default_tags=["分析", "数据", "报告"],
    ),
    AgentRole.RESEARCHER: RoleTemplate(
        role=AgentRole.RESEARCHER,
        display_name="研究员",
        description="信息检索和资料整理。搜索 → 整理 → 输出摘要。",
        default_capabilities=[
            CapabilityDecl(name="web_search", type=CapabilityType.TOOL, description="网络搜索"),
            CapabilityDecl(name="information_analysis", type=CapabilityType.SKILL, description="信息分析"),
        ],
        default_tags=["搜索", "研究", "整理"],
    ),
    AgentRole.SECRETARY: RoleTemplate(
        role=AgentRole.SECRETARY,
        display_name="秘书",
        description="日程管理和任务提醒。维护用户偏好和日程。",
        default_capabilities=[
            CapabilityDecl(name="schedule_management", type=CapabilityType.SKILL, description="日程管理"),
            CapabilityDecl(name="notification", type=CapabilityType.TOOL, description="消息通知"),
        ],
        default_tags=["日程", "提醒", "管理"],
    ),
    AgentRole.ASSISTANT: RoleTemplate(
        role=AgentRole.ASSISTANT,
        display_name="通用助手",
        description="通用问答和任务执行。根据指令动态适配工具组合。",
        default_capabilities=[],
        default_tags=["通用", "助手"],
    ),
    AgentRole.ORCHESTRATOR: RoleTemplate(
        role=AgentRole.ORCHESTRATOR,
        display_name="协调者",
        description="多 Agent 任务编排。分解任务 → 委托 → 整合结果。",
        default_capabilities=[
            CapabilityDecl(name="task_decomposition", type=CapabilityType.SKILL, description="任务分解"),
            CapabilityDecl(name="agent_orchestration", type=CapabilityType.SKILL, description="Agent 编排"),
        ],
        default_tags=["编排", "协调", "委托"],
    ),
    AgentRole.CRITIC: RoleTemplate(
        role=AgentRole.CRITIC,
        display_name="审阅者",
        description="审核和纠错。审查 Agent 输出，提供反馈。",
        default_capabilities=[
            CapabilityDecl(name="quality_review", type=CapabilityType.SKILL, description="质量审查"),
            CapabilityDecl(name="feedback", type=CapabilityType.TOOL, description="反馈输出"),
        ],
        default_tags=["审核", "质量", "反馈"],
    ),
}


class RoleRegistry(ABC):
    """角色模板注册中心。"""

    @abstractmethod
    async def get_template(self, role: AgentRole) -> RoleTemplate | None:
        """获取指定角色的模板。"""
        ...

    @abstractmethod
    async def register_template(self, template: RoleTemplate) -> None:
        """注册自定义角色模板。"""
        ...

    @abstractmethod
    async def list_templates(self) -> list[RoleTemplate]:
        """列出所有可用角色模板（内置 + 自定义）。"""
        ...

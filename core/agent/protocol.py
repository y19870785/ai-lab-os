"""Agent Runtime 抽象接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.agent.models import AgentFilter, AgentInstance, AgentSpec, AgentStatus


class AgentRuntime(ABC):
    """Agent 运行时管理。"""

    @abstractmethod
    async def register(self, spec: AgentSpec) -> str:
        """注册一个新的 Agent 类型。返回 agent_id。"""
        ...

    @abstractmethod
    async def unregister(self, agent_id: str) -> None:
        """注销一个 Agent。"""
        ...

    @abstractmethod
    async def start(self, agent_id: str) -> None:
        """启动一个 Agent 实例。"""
        ...

    @abstractmethod
    async def stop(self, agent_id: str) -> None:
        """停止一个 Agent 实例。"""
        ...

    @abstractmethod
    async def get_status(self, agent_id: str) -> AgentStatus:
        """查询 Agent 当前状态。"""
        ...

    @abstractmethod
    async def list_agents(self, filter: AgentFilter | None = None) -> list[AgentInstance]:
        """列出所有 Agent 实例，可按条件过滤。"""
        ...

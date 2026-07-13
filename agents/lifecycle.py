"""Agent 生命周期管理。定义 Agent 从创建到退役的完整状态机。

区别于 Core Layer 的 AgentRuntime（实例启停），
这里是业务生命周期——包含身份注册、能力绑定、记忆初始化等完整流程。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

from pydantic import BaseModel


class AgentLifecycleState(str, Enum):
    """Agent 业务生命周期状态。"""
    DEFINED = "defined"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    DISABLED = "disabled"
    RETIRED = "retired"


# 合法状态转换表
TRANSITIONS: dict[AgentLifecycleState, list[AgentLifecycleState]] = {
    AgentLifecycleState.DEFINED: [AgentLifecycleState.INITIALIZED],
    AgentLifecycleState.INITIALIZED: [AgentLifecycleState.ACTIVE, AgentLifecycleState.ERROR],
    AgentLifecycleState.ACTIVE: [AgentLifecycleState.RUNNING, AgentLifecycleState.PAUSED, AgentLifecycleState.DISABLED, AgentLifecycleState.ERROR],
    AgentLifecycleState.RUNNING: [AgentLifecycleState.ACTIVE, AgentLifecycleState.ERROR],
    AgentLifecycleState.PAUSED: [AgentLifecycleState.ACTIVE, AgentLifecycleState.ERROR],
    AgentLifecycleState.ERROR: [AgentLifecycleState.ACTIVE, AgentLifecycleState.DISABLED],
    AgentLifecycleState.DISABLED: [AgentLifecycleState.RETIRED, AgentLifecycleState.ACTIVE],
    AgentLifecycleState.RETIRED: [],
}


class InvalidTransitionError(ValueError):
    """非法的状态转换。"""
    pass


class AgentLifecycleManager(ABC):
    """Agent 生命周期管理器。管理 Agent 的完整业务生命周期。"""

    @abstractmethod
    async def define(self, identity: "agents.identity.AgentIdentity") -> str:  # noqa: F821
        """注册一个新的 Agent 身份。返回 agent_id。"""
        ...

    @abstractmethod
    async def initialize(self, agent_id: str) -> None:
        """初始化 Agent：绑定能力、初始化记忆、配置权限。"""
        ...

    @abstractmethod
    async def activate(self, agent_id: str) -> None:
        """激活 Agent：使其可接收任务。"""
        ...

    @abstractmethod
    async def run(self, agent_id: str, task: "agents.context.AgentTask") -> "agents.context.AgentResult":  # noqa: F821
        """执行一个任务。"""
        ...

    @abstractmethod
    async def pause(self, agent_id: str) -> None:
        """暂停 Agent。"""
        ...

    @abstractmethod
    async def disable(self, agent_id: str) -> None:
        """禁用 Agent（管理员操作）。"""
        ...

    @abstractmethod
    async def retire(self, agent_id: str) -> None:
        """退役 Agent。保留记录但不可再激活。"""
        ...

    @abstractmethod
    async def get_state(self, agent_id: str) -> AgentLifecycleState:
        """查询 Agent 当前生命周期状态。"""
        ...

    def validate_transition(self, current: AgentLifecycleState, target: AgentLifecycleState) -> None:
        """验证状态转换是否合法。"""
        allowed = TRANSITIONS.get(current, [])
        if target not in allowed:
            raise InvalidTransitionError(
                f"不允许的转换: {current.value} → {target.value}。"
                f"允许的目标: {[s.value for s in allowed]}"
            )

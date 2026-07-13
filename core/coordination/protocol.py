"""Multi-Agent Coordination Protocol.

定义 Orchestrator、MessageBus、Delegator、Merger 的抽象接口。
遵循 Protocol First 原则，所有实现必须实现这些接口。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any

from core.coordination.models import (
    AgentMessage, AgentMessageResponse, AgentTask, AgentRole,
    CollaborationContext, CoordinationResult, TeamConfig,
    DelegationStatus, CoordinationStatus,
)


class MessageBusProtocol(ABC):
    """Agent 间消息总线接口。"""

    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def shutdown(self) -> None: ...
    @abstractmethod
    async def send(self, message: AgentMessage) -> str: ...
    @abstractmethod
    async def broadcast(self, message: AgentMessage) -> list[str]: ...
    @abstractmethod
    async def request(self, message: AgentMessage, timeout: float = 30.0) -> AgentMessageResponse: ...
    @abstractmethod
    async def get_messages(self, agent_id: str) -> list[AgentMessage]: ...
    @abstractmethod
    def message_count(self) -> int: ...


class DelegationProtocol(ABC):
    """任务委派接口。"""

    @abstractmethod
    async def delegate(self, task: AgentTask) -> str: ...
    @abstractmethod
    async def get_status(self, task_id: str) -> DelegationStatus: ...
    @abstractmethod
    async def get_result(self, task_id: str) -> dict[str, Any]: ...
    @abstractmethod
    async def cancel(self, task_id: str) -> bool: ...
    @abstractmethod
    async def list_tasks(self, agent_id: str = "") -> list[AgentTask]: ...


class MergerProtocol(ABC):
    """结果合并接口。"""

    @abstractmethod
    async def merge(self, results: dict[str, Any], context: CollaborationContext) -> str: ...
    @abstractmethod
    def strategy(self) -> str: ...


class OrchestratorProtocol(ABC):
    """Agent Orchestrator 接口 —— 多 Agent 协作唯一入口。"""

    @abstractmethod
    async def initialize(self) -> None: ...
    @abstractmethod
    async def shutdown(self) -> None: ...
    @abstractmethod
    async def create_team(self, config: TeamConfig) -> None: ...
    @abstractmethod
    async def coordinate(self, goal: str, context: dict[str, Any] | None = None) -> CoordinationResult: ...
    @abstractmethod
    async def get_context(self, session_id: str) -> CollaborationContext | None: ...
    @abstractmethod
    async def cancel(self, session_id: str) -> bool: ...
    @abstractmethod
    def status(self, session_id: str) -> CoordinationStatus: ...

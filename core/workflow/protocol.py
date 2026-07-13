"""WorkflowProtocol —— 所有 Workflow 必须实现的统一接口"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.workflow.models import WorkflowInfo, WorkflowPlan, WorkflowRequest, WorkflowResult


class WorkflowProtocol(ABC):
    """Workflow 抽象接口

    每个具体的 Workflow（如 InvestmentResearch、QuoteGeneration）
    都实现此接口，定义自己的步骤计划。
    """

    @abstractmethod
    async def initialize(self) -> None:
        """初始化 Workflow"""
        ...

    @abstractmethod
    async def plan(self, request: WorkflowRequest) -> WorkflowPlan:
        """生成执行计划"""
        ...

    @abstractmethod
    async def execute(self, request: WorkflowRequest) -> WorkflowResult:
        """执行 Workflow"""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """关闭 Workflow"""
        ...

    @property
    @abstractmethod
    def info(self) -> WorkflowInfo:
        """Workflow 元数据"""
        ...

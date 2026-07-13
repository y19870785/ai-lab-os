"""Planner —— 根据 WorkflowRequest 生成执行计划。

当前版本：Rule-based Planner（基于规则）。
后续可替换为 LLM Planner、Tree Planner、Graph Planner。
采用策略模式，通过 PlannerType 切换。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.workflow.models import WorkflowPlan, WorkflowStep, WorkflowRequest, StepType


class PlannerProtocol(ABC):
    """Planner 抽象接口 —— 策略模式"""

    @abstractmethod
    async def plan(self, request: WorkflowRequest, steps: list[WorkflowStep]) -> WorkflowPlan:
        """根据请求和预定义步骤生成执行计划"""
        ...


class RulePlanner(PlannerProtocol):
    """基于规则的 Planner —— 直接使用预定义步骤，不做动态规划"""

    async def plan(self, request: WorkflowRequest, steps: list[WorkflowStep]) -> WorkflowPlan:
        return WorkflowPlan(
            workflow_id=request.workflow_id,
            steps=steps,
            estimated_steps=len(steps),
        )


def get_planner(planner_type: str = "rule") -> PlannerProtocol:
    """工厂方法：根据类型获取 Planner"""
    if planner_type == "rule":
        return RulePlanner()
    # 未来扩展: llm / tree / graph
    raise ValueError(f"Unknown planner type: {planner_type}")

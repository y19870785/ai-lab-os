"""TaskPlanner —— 根据 Workflow 列表和依赖关系生成执行计划。

当前版本：RuleTaskPlanner（基于规则）。
未来：LLMTaskPlanner / GraphPlanner / TreePlanner。
策略模式，不得修改 Runtime。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from core.task.models import TaskRequest, TaskDependency, DependencyType


class TaskPlannerProtocol(ABC):
    """Task Planner 抽象接口"""

    @abstractmethod
    async def plan(self, request: TaskRequest) -> list[str]:
        """返回按执行顺序排列的 workflow_name 列表"""
        ...


class RuleTaskPlanner(TaskPlannerProtocol):
    """基于规则的 Planner —— 直接使用请求中的 workflow_names 顺序"""

    async def plan(self, request: TaskRequest) -> list[str]:
        # 如果有依赖，按依赖排序（AFTER 类型的依赖排在前面）
        if not request.dependencies:
            return request.workflow_names

        # 简易拓扑排序：AFTER 依赖排在最前面
        ordered = []
        remaining = list(request.workflow_names)
        dep_ids = {d.depends_on_task_id for d in request.dependencies}

        # 先把依赖中引用的 task 放在前面（这里简化：workflow_names 本身就是有序的）
        for wf in request.workflow_names:
            if wf not in dep_ids:
                ordered.append(wf)
        for wf in request.workflow_names:
            if wf in dep_ids:
                ordered.append(wf)

        return ordered if ordered else request.workflow_names


def get_task_planner(planner_type: str = "rule") -> TaskPlannerProtocol:
    if planner_type == "rule":
        return RuleTaskPlanner()
    raise ValueError(f"Unknown planner type: {planner_type}")

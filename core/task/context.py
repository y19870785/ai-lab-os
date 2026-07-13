"""TaskContextManager —— 管理跨 Workflow 共享上下文。

统一保存 Variables / Memory IDs / Knowledge IDs / Workflow IDs / Agent IDs。
不散落多个模块。
"""

from __future__ import annotations
from core.task.models import TaskContext


class ContextManager:
    """Task 上下文管理器"""

    def __init__(self):
        self._contexts: dict[str, TaskContext] = {}

    def create(self, task_id: str, variables: dict | None = None) -> TaskContext:
        ctx = TaskContext(task_id=task_id, variables=variables or {})
        self._contexts[task_id] = ctx
        return ctx

    def get(self, task_id: str) -> TaskContext | None:
        return self._contexts.get(task_id)

    def update_variables(self, task_id: str, updates: dict) -> None:
        ctx = self._contexts.get(task_id)
        if ctx:
            ctx.variables.update(updates)

    def add_memory(self, task_id: str, memory_id: str) -> None:
        ctx = self._contexts.get(task_id)
        if ctx and memory_id not in ctx.memory_ids:
            ctx.memory_ids.append(memory_id)

    def add_workflow(self, task_id: str, workflow_id: str) -> None:
        ctx = self._contexts.get(task_id)
        if ctx and workflow_id not in ctx.workflow_ids:
            ctx.workflow_ids.append(workflow_id)

    def add_agent(self, task_id: str, agent_id: str) -> None:
        ctx = self._contexts.get(task_id)
        if ctx and agent_id not in ctx.agent_ids:
            ctx.agent_ids.append(agent_id)

    def add_checkpoint(self, task_id: str, checkpoint_id: str) -> None:
        ctx = self._contexts.get(task_id)
        if ctx and checkpoint_id not in ctx.checkpoint_ids:
            ctx.checkpoint_ids.append(checkpoint_id)

    def remove(self, task_id: str) -> None:
        self._contexts.pop(task_id, None)

    def exists(self, task_id: str) -> bool:
        return task_id in self._contexts

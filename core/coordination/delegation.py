"""Task Delegator —— Agent 间任务委派。

复用 Task Runtime 和 Workflow Runtime 进行委派执行。
不直接操作 Provider/Tool/Database。
"""

from __future__ import annotations

import asyncio
from typing import Any

from core.coordination.models import (
    AgentTask, DelegationStatus,
)
from core.coordination.protocol import DelegationProtocol
from core.coordination.events import publish_coordination_event, CoordinationEventTypes
from core.coordination.exceptions import DelegationError
from core.coordination.config import CoordinationConfig


class TaskDelegator(DelegationProtocol):
    """Agent 任务委派器。

    将 AgentTask 委派给 Task Runtime 执行。
    支持超时、重试、状态追踪。
    """

    def __init__(
        self,
        task_runtime=None,
        agent_registry=None,
        bus=None,
        config: CoordinationConfig | None = None,
    ):
        self._task_runtime = task_runtime
        self._agent_registry = agent_registry
        self._bus = bus
        self._config = config or CoordinationConfig()
        self._tasks: dict[str, AgentTask] = {}
        self._results: dict[str, dict[str, Any]] = {}

    async def delegate(self, task: AgentTask) -> str:
        """委派一个任务给 Agent。"""
        self._tasks[task.task_id] = task
        task.status = DelegationStatus.ACCEPTED

        await publish_coordination_event(
            self._bus,
            CoordinationEventTypes.TASK_DELEGATED,
            payload={
                "task_id": task.task_id,
                "assigned_agent": task.assigned_agent,
                "title": task.title,
            },
        )

        # 如果有 Task Runtime，通过它执行
        if self._task_runtime:
            try:
                from core.task.models import TaskRequest, TaskType, TaskPriority
                req = TaskRequest(
                    task_name=task.title,
                    task_type=TaskType.ONE_SHOT,
                    priority=TaskPriority.NORMAL,
                    workflow_names=task.input_data.get("workflow_names", []),
                    variables=task.input_data,
                    timeout=task.timeout,
                    max_retries=task.max_retries,
                    agent_id=task.assigned_agent,
                    metadata={"parent_task_id": task.parent_task_id},
                )
                info = await self._task_runtime.create_task(req)
                task.status = DelegationStatus.RUNNING
                result = await asyncio.wait_for(
                    self._task_runtime.run(info.id),
                    timeout=task.timeout,
                )
                task.result = result.model_dump() if hasattr(result, 'model_dump') else {"status": str(result)}
                task.status = DelegationStatus.COMPLETED if result.status.value == "completed" else DelegationStatus.FAILED
                if task.status == DelegationStatus.FAILED:
                    task.error = "; ".join(result.errors) if hasattr(result, 'errors') else str(result)
                self._results[task.task_id] = task.result
            except asyncio.TimeoutError:
                task.status = DelegationStatus.TIMEOUT
                task.error = f"Timeout after {task.timeout}s"
            except Exception as e:
                task.status = DelegationStatus.FAILED
                task.error = str(e)
        else:
            # 无 Task Runtime：标记为完成（测试模式）
            task.status = DelegationStatus.COMPLETED
            task.result = {"status": "ok", "note": "no task runtime (mock mode)"}
            self._results[task.task_id] = task.result

        # 发布事件
        event_type = (
            CoordinationEventTypes.TASK_COMPLETED
            if task.status == DelegationStatus.COMPLETED
            else CoordinationEventTypes.TASK_FAILED
        )
        await publish_coordination_event(
            self._bus,
            event_type,
            payload={"task_id": task.task_id, "status": task.status.value},
        )

        return task.task_id

    async def get_status(self, task_id: str) -> DelegationStatus:
        task = self._tasks.get(task_id)
        if task is None:
            raise DelegationError(task_id, "not found")
        return task.status

    async def get_result(self, task_id: str) -> dict[str, Any]:
        return self._results.get(task_id, {})

    async def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        if self._task_runtime:
            await self._task_runtime.cancel(task_id)
        task.status = DelegationStatus.REJECTED
        return True

    async def list_tasks(self, agent_id: str = "") -> list[AgentTask]:
        if agent_id:
            return [t for t in self._tasks.values() if t.assigned_agent == agent_id]
        return list(self._tasks.values())

    @property
    def task_count(self) -> int:
        return len(self._tasks)

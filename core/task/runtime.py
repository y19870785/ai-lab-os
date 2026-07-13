"""TaskRuntime —— AI-Lab 统一任务编排中心。

职责：
1. 管理 Task 的完整生命周期（11 状态）
2. 按 Planner 生成的顺序执行多个 Workflow
3. 管理跨 Workflow 共享上下文（TaskContext）
4. 解析 Task 间依赖关系（DependencyResolver）
5. 每步保存 Checkpoint
6. 发布事件

Task Runtime 是 Scheduler + Workflow 之上的统一协调层。
Task 不直接调用 Tool / Provider / MCP，只委托 Workflow Runtime。
"""

from __future__ import annotations
import asyncio
import time

from core.task.models import (
    TaskInfo, TaskRequest, TaskResult, TaskStatus, TaskCheckpoint,
    TaskContext, TaskType,
)
from core.task.protocol import TaskProtocol
from core.task.registry import TaskRegistry
from core.task.manager import TaskManager
from core.task.planner import get_task_planner, TaskPlannerProtocol
from core.task.state import TaskStateMachine
from core.task.dependencies import DependencyResolver
from core.task.context import ContextManager
from core.task.checkpoint import CheckpointManager
from core.task.config import TaskConfig
from core.task.events import publish_task_event, TaskEventTypes
from core.task.exceptions import (
    TaskError, TaskNotFoundError, TaskStateError, TaskTimeout,
    TaskCancelled, TaskExecutionError,
)


class TaskRuntime(TaskProtocol):
    """Task 运行时 —— 统一任务编排中心"""

    def __init__(
        self,
        manager: TaskManager | None = None,
        workflow_runtime=None,
        scheduler_runtime=None,
        planner: TaskPlannerProtocol | None = None,
        context_mgr: ContextManager | None = None,
        checkpoint_mgr: CheckpointManager | None = None,
        config: TaskConfig | None = None,
        bus=None,
    ):
        self._manager = manager or TaskManager()
        self._workflow_runtime = workflow_runtime
        self._scheduler_runtime = scheduler_runtime
        self._planner = planner or get_task_planner("rule")
        self._context_mgr = context_mgr or ContextManager()
        self._checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self._config = config or TaskConfig()
        self._bus = bus
        self._state_machines: dict[str, TaskStateMachine] = {}
        self._cancel_flags: dict[str, bool] = {}

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        for task_id in list(self._cancel_flags.keys()):
            self._cancel_flags[task_id] = True

    # ---- Task 管理 ----

    async def create_task(self, request: TaskRequest) -> TaskInfo:
        info = TaskInfo(
            name=request.task_name,
            task_type=request.task_type,
            priority=request.priority,
            tags=request.metadata.get("tags", []),
        )
        self._manager.register(info, TaskStatus.CREATED)
        self._state_machines[info.id] = TaskStateMachine(TaskStatus.CREATED)
        self._context_mgr.create(info.id, request.variables)

        await publish_task_event(self._bus, TaskEventTypes.CREATED,
                                 info.id, info.name)
        return info

    async def run(self, task_id: str) -> TaskResult:
        info = self._manager.get(task_id)
        sm = self._state_machines[info.id]
        sm.transition(TaskStatus.READY)

        await publish_task_event(self._bus, TaskEventTypes.STARTED,
                                 info.id, info.name)
        sm.transition(TaskStatus.RUNNING)
        await publish_task_event(self._bus, TaskEventTypes.RUNNING,
                                 info.id, info.name)

        # 检查是否有快照可恢复
        cp = self._checkpoint_mgr.load(task_id)
        start_idx = cp.current_workflow_index if cp else 0

        # 获取执行计划（从注册的请求中获取 workflow_names）
        # 这里用 context 中的变量或默认空列表
        workflow_names = self._context_mgr.get(task_id)
        wf_list = workflow_names.variables.get("workflow_names", []) if workflow_names else []

        t0 = time.time()
        errors = []
        outputs = {}
        retry_count = 0

        for i in range(start_idx, len(wf_list)):
            if self._cancel_flags.get(task_id):
                sm.transition(TaskStatus.CANCELLED)
                await publish_task_event(self._bus, TaskEventTypes.CANCELLED, info.id, info.name)
                return TaskResult(task_id=task_id, status=TaskStatus.CANCELLED,
                                  total_latency_ms=(time.time() - t0) * 1000)

            wf_name = wf_list[i]
            try:
                if self._workflow_runtime:
                    from core.workflow.models import WorkflowRequest
                    wf_req = WorkflowRequest(workflow_name=wf_name)
                    wf_result = await asyncio.wait_for(
                        self._workflow_runtime.run(wf_req),
                        timeout=self._config.default_timeout,
                    )
                    outputs[wf_name] = wf_result.outputs if hasattr(wf_result, 'outputs') else str(wf_result)
                else:
                    await asyncio.sleep(0.01)
                    outputs[wf_name] = {"status": "ok", "note": "no workflow runtime"}

                self._context_mgr.add_workflow(task_id, wf_name)

            except asyncio.TimeoutError:
                errors.append(f"Workflow {wf_name} timed out")
                retry_count += 1
                if retry_count >= self._config.max_retries:
                    sm.transition(TaskStatus.TIMEOUT)
                    await publish_task_event(self._bus, TaskEventTypes.TIMEOUT, info.id, info.name)
                    return TaskResult(task_id=task_id, status=TaskStatus.TIMEOUT,
                                      total_latency_ms=(time.time() - t0) * 1000, errors=errors)
                else:
                    await publish_task_event(self._bus, TaskEventTypes.RETRY, info.id, info.name,
                                             {"retry": retry_count, "workflow": wf_name})
                    # 重试当前 workflow
                    i -= 1
                    continue

            except Exception as e:
                errors.append(f"Workflow {wf_name}: {e}")
                retry_count += 1
                if retry_count >= self._config.max_retries:
                    sm.transition(TaskStatus.FAILED)
                    await publish_task_event(self._bus, TaskEventTypes.FAILED, info.id, info.name,
                                             {"errors": errors})
                    return TaskResult(task_id=task_id, status=TaskStatus.FAILED,
                                      total_latency_ms=(time.time() - t0) * 1000, errors=errors)

            # 保存快照
            self._checkpoint_mgr.save(TaskCheckpoint(
                task_id=task_id,
                status=sm.current,
                current_workflow_index=i + 1,
                completed_workflows=list(outputs.keys()),
                context=self._context_mgr.get(task_id) or TaskContext(),
                retry_count=retry_count,
            ))

            # 更新状态
            self._manager.set_status(task_id, sm.current)
            retry_count = 0

        # 完成
        sm.transition(TaskStatus.COMPLETED)
        self._manager.set_status(task_id, TaskStatus.COMPLETED)
        await publish_task_event(self._bus, TaskEventTypes.COMPLETED, info.id, info.name)

        total_ms = (time.time() - t0) * 1000
        return TaskResult(
            task_id=task_id, status=TaskStatus.COMPLETED,
            workflow_results=outputs, total_latency_ms=total_ms, errors=errors,
            outputs=outputs,
        )

    async def pause(self, task_id: str) -> bool:
        sm = self._state_machines.get(task_id)
        if sm is None or not sm.can_transition(TaskStatus.PAUSED):
            return False
        sm.transition(TaskStatus.PAUSED)
        self._manager.set_status(task_id, TaskStatus.PAUSED)
        await publish_task_event(self._bus, TaskEventTypes.PAUSED, task_id)
        return True

    async def resume(self, task_id: str) -> bool:
        sm = self._state_machines.get(task_id)
        if sm is None or sm.current != TaskStatus.PAUSED:
            return False
        sm.transition(TaskStatus.RUNNING)
        self._manager.set_status(task_id, TaskStatus.RUNNING)
        await publish_task_event(self._bus, TaskEventTypes.RESUMED, task_id)
        # 继续执行 run
        return True

    async def cancel(self, task_id: str) -> bool:
        self._cancel_flags[task_id] = True
        sm = self._state_machines.get(task_id)
        if sm:
            sm.transition(TaskStatus.CANCELLED)
            self._manager.set_status(task_id, TaskStatus.CANCELLED)
        await publish_task_event(self._bus, TaskEventTypes.CANCELLED, task_id)
        return True

    async def retry(self, task_id: str) -> bool:
        sm = self._state_machines.get(task_id)
        if sm is None or not sm.can_transition(TaskStatus.RETRYING):
            return False
        sm.transition(TaskStatus.RETRYING)
        await publish_task_event(self._bus, TaskEventTypes.RETRY, task_id)
        return True

    async def destroy(self, task_id: str) -> bool:
        self._cancel_flags.pop(task_id, None)
        self._state_machines.pop(task_id, None)
        self._context_mgr.remove(task_id)
        self._checkpoint_mgr.delete(task_id)
        self._manager.unregister(task_id)
        await publish_task_event(self._bus, TaskEventTypes.DESTROYED, task_id)
        return True

    async def query(self, task_id: str) -> TaskInfo | None:
        try:
            return self._manager.get(task_id)
        except TaskNotFoundError:
            return None

    async def list_tasks(self) -> list[TaskInfo]:
        return self._manager.list()

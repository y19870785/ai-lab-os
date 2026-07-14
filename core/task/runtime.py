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
from core.errors import (
    ErrorCategory,
    FailureInfo,
    failure_event_payload,
    failure_from_exception,
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
        variables = dict(request.variables)
        if request.workflow_names or "workflow_names" not in variables:
            variables["workflow_names"] = list(request.workflow_names)
        variables["_task_max_retries"] = request.max_retries
        variables["_task_timeout"] = request.timeout
        variables["_task_trace_id"] = request.trace_id
        self._context_mgr.create(info.id, variables)

        await publish_task_event(self._bus, TaskEventTypes.CREATED,
                                 info.id, info.name)
        return info

    async def run(self, task_id: str) -> TaskResult:
        info = self._manager.get(task_id)
        sm = self._state_machines[info.id]
        sm.transition(TaskStatus.READY)
        self._manager.set_status(task_id, TaskStatus.READY)

        await publish_task_event(self._bus, TaskEventTypes.STARTED,
                                 info.id, info.name)
        sm.transition(TaskStatus.RUNNING)
        self._manager.set_status(task_id, TaskStatus.RUNNING)
        await publish_task_event(self._bus, TaskEventTypes.RUNNING,
                                 info.id, info.name)

        cp = self._checkpoint_mgr.load(task_id)
        start_idx = cp.current_workflow_index if cp else 0
        context = self._context_mgr.get(task_id)
        variables = context.variables if context else {}
        wf_list = list(variables.get("workflow_names", []))
        trace_id = str(variables.get("_task_trace_id", ""))
        max_retries = max(0, int(variables.get("_task_max_retries", self._config.max_retries)))
        timeout = max(1, int(variables.get("_task_timeout", self._config.default_timeout)))
        t0 = time.time()
        outputs: dict[str, object] = {}
        retry_count = cp.retry_count if cp else 0

        if not wf_list:
            failure = FailureInfo(
                code="task.plan.empty",
                category=ErrorCategory.VALIDATION,
                message="Task execution plan is empty",
                component="task.runtime",
                operation="plan",
                retryable=False,
                trace_id=trace_id,
            )
            return await self._terminal_failure(
                info, sm, failure, TaskStatus.FAILED, t0, retry_count,
            )

        if self._workflow_runtime is None:
            failure = FailureInfo(
                code="task.workflow.not_configured",
                category=ErrorCategory.NOT_CONFIGURED,
                message="WorkflowRuntime is not configured",
                component="task.runtime",
                operation="workflow.execute",
                retryable=False,
                trace_id=trace_id,
            )
            return await self._terminal_failure(
                info, sm, failure, TaskStatus.FAILED, t0, retry_count,
            )

        for i in range(start_idx, len(wf_list)):
            if self._cancel_flags.get(task_id):
                sm.transition(TaskStatus.CANCELLED)
                self._manager.set_status(task_id, TaskStatus.CANCELLED)
                await publish_task_event(self._bus, TaskEventTypes.CANCELLED, info.id, info.name)
                return TaskResult(task_id=task_id, status=TaskStatus.CANCELLED,
                                  total_latency_ms=(time.time() - t0) * 1000,
                                  trace_id=trace_id)

            wf_name = wf_list[i]
            attempt = 0
            while True:
                attempt += 1
                try:
                    from core.workflow.models import WorkflowRequest
                    wf_req = WorkflowRequest(workflow_name=wf_name, trace_id=trace_id)
                    wf_result = await asyncio.wait_for(
                        self._workflow_runtime.run(wf_req),
                        timeout=timeout,
                    )
                    if getattr(wf_result.status, "value", wf_result.status) != "completed":
                        message = "; ".join(getattr(wf_result, "errors", [])) or "Workflow failed"
                        raise TaskExecutionError(message)
                    outputs[wf_name] = getattr(wf_result, "outputs", {})
                    self._context_mgr.add_workflow(task_id, wf_name)
                    break
                except asyncio.TimeoutError as exc:
                    failure = failure_from_exception(
                        exc,
                        component="task.workflow",
                        operation="execute",
                        trace_id=trace_id,
                        code="task.workflow.timeout",
                        category=ErrorCategory.TIMEOUT,
                        retryable=True,
                        details={"workflow": wf_name, "attempt": attempt},
                    )
                    terminal_status = TaskStatus.TIMEOUT
                except Exception as exc:
                    failure = failure_from_exception(
                        exc,
                        component="task.workflow",
                        operation="execute",
                        trace_id=trace_id,
                        code="task.workflow.execution_failed",
                        category=ErrorCategory.DEPENDENCY_FAILURE,
                        retryable=True,
                        details={"workflow": wf_name, "attempt": attempt},
                    )
                    terminal_status = TaskStatus.FAILED

                if attempt > max_retries:
                    return await self._terminal_failure(
                        info, sm, failure, terminal_status, t0, retry_count,
                        outputs=outputs,
                    )

                retry_count += 1
                await publish_task_event(
                    self._bus,
                    TaskEventTypes.RETRY,
                    info.id,
                    info.name,
                    {
                        **failure_event_payload(failure, status="retrying"),
                        "workflow": wf_name,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "max_attempts": max_retries + 1,
                    },
                )

            self._checkpoint_mgr.save(TaskCheckpoint(
                task_id=task_id,
                status=sm.current,
                current_workflow_index=i + 1,
                completed_workflows=list(outputs.keys()),
                context=self._context_mgr.get(task_id) or TaskContext(),
                retry_count=retry_count,
            ))
            self._manager.set_status(task_id, sm.current)

        sm.transition(TaskStatus.COMPLETED)
        self._manager.set_status(task_id, TaskStatus.COMPLETED)
        await publish_task_event(self._bus, TaskEventTypes.COMPLETED, info.id, info.name)

        total_ms = (time.time() - t0) * 1000
        return TaskResult(
            task_id=task_id, status=TaskStatus.COMPLETED,
            workflow_results=outputs, total_latency_ms=total_ms, errors=[],
            outputs=outputs, retry_count=retry_count, trace_id=trace_id,
        )

    async def _terminal_failure(
        self,
        info: TaskInfo,
        sm: TaskStateMachine,
        failure: FailureInfo,
        status: TaskStatus,
        started_at: float,
        retry_count: int,
        *,
        outputs: dict[str, object] | None = None,
    ) -> TaskResult:
        sm.transition(status)
        self._manager.set_status(info.id, status)
        event_type = TaskEventTypes.TIMEOUT if status == TaskStatus.TIMEOUT else TaskEventTypes.FAILED
        await publish_task_event(
            self._bus,
            event_type,
            info.id,
            info.name,
            failure_event_payload(failure),
        )
        return TaskResult(
            task_id=info.id,
            status=status,
            workflow_results=outputs or {},
            outputs=outputs or {},
            total_latency_ms=(time.time() - started_at) * 1000,
            retry_count=retry_count,
            errors=[failure.message],
            trace_id=failure.trace_id,
            retryable=failure.retryable,
            failure=failure,
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

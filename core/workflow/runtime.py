"""WorkflowRuntime —— Workflow 执行的顶层调度器。

职责：
1. 接收 WorkflowRequest
2. 从 Registry 获取 Workflow 定义
3. 调用 Planner 生成执行计划
4. 委托 Executor 执行
5. 管理生命周期
6. 发布事件

WorkflowRuntime 是 Workflow 层的唯一对外入口。
"""

from __future__ import annotations

from core.workflow.models import (
    WorkflowRequest, WorkflowResult, WorkflowStatus, WorkflowInfo, WorkflowStep,
)
from core.workflow.protocol import WorkflowProtocol
from core.workflow.registry import WorkflowRegistry
from core.workflow.executor import WorkflowExecutor
from core.workflow.planner import get_planner
from core.workflow.state import WorkflowStateMachine
from core.workflow.events import publish_workflow_event, WorkflowEventTypes
from core.workflow.config import WorkflowConfig
from core.workflow.exceptions import WorkflowNotFoundError, WorkflowStateError


class WorkflowRuntime:
    """Workflow 运行时 —— 统一入口"""

    def __init__(
        self,
        registry: WorkflowRegistry,
        executor: WorkflowExecutor | None = None,
        config: WorkflowConfig | None = None,
        bus=None,
    ):
        self._registry = registry
        self._executor = executor
        self._config = config or WorkflowConfig()
        self._bus = bus
        self._active: dict[str, WorkflowStateMachine] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the runtime idempotently."""
        self._initialized = True

    async def shutdown(self) -> None:
        """Release runtime state idempotently."""
        self._active.clear()
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def run(self, request: WorkflowRequest) -> WorkflowResult:
        """执行一个 Workflow

        流程：查找 → 状态机 → Planner → Executor → 事件 → 返回
        """
        # 1. 查找 Workflow
        wf_name = request.workflow_name
        if not self._registry.exists(wf_name):
            raise WorkflowNotFoundError(f"Workflow not found: {wf_name}")

        wf_info = self._registry.get_info(wf_name)
        wf_instance = self._registry.get(wf_name)

        # 2. 初始化
        await wf_instance.initialize()
        state = WorkflowStateMachine(WorkflowStatus.CREATED)
        state.transition(WorkflowStatus.READY)
        self._active[wf_info.id] = state

        await publish_workflow_event(
            self._bus, WorkflowEventTypes.CREATED,
            wf_info.id, request.agent_id, request.session_id,
        )

        try:
            # 3. Planning
            state.transition(WorkflowStatus.PLANNING)
            planner = get_planner(self._config.planner_type)
            plan = await wf_instance.plan(request)
            if not plan.steps:
                # 使用 planner 处理
                plan = await planner.plan(request, plan.steps)
            if not plan.steps:
                plan = await planner.plan(request, await wf_instance.plan(request)).steps and plan

            # 确保 plan.workflow_id 已设置
            if not plan.workflow_id:
                plan.workflow_id = wf_info.id

            # 4. Execution
            state.transition(WorkflowStatus.RUNNING)
            await publish_workflow_event(
                self._bus, WorkflowEventTypes.STARTED,
                wf_info.id, request.agent_id, request.session_id,
            )

            executor = self._executor or WorkflowExecutor(
                bus=self._bus,
                config=self._config,
            )
            result = await executor.execute(plan, request)

            # 5. Completion
            if result.status == WorkflowStatus.COMPLETED:
                state.transition(WorkflowStatus.COMPLETED)
                await publish_workflow_event(
                    self._bus, WorkflowEventTypes.COMPLETED,
                    wf_info.id, request.agent_id, request.session_id,
                    {"steps_completed": result.steps_completed},
                )
            else:
                state.transition(WorkflowStatus.FAILED)
                await publish_workflow_event(
                    self._bus, WorkflowEventTypes.FAILED,
                    wf_info.id, request.agent_id, request.session_id,
                    {"errors": result.errors},
                )

            return result

        except Exception:
            state.transition(WorkflowStatus.FAILED)
            await publish_workflow_event(
                self._bus, WorkflowEventTypes.FAILED,
                wf_info.id, request.agent_id, request.session_id,
            )
            raise

        finally:
            await wf_instance.shutdown()

    async def cancel(self, workflow_id: str) -> bool:
        """取消正在运行的 Workflow"""
        state = self._active.get(workflow_id)
        if state is None:
            return False
        state.transition(WorkflowStatus.CANCELLED)
        await publish_workflow_event(
            self._bus, WorkflowEventTypes.CANCELLED,
            workflow_id,
        )
        return True

    @property
    def registry(self) -> WorkflowRegistry:
        return self._registry

    @property
    def active_count(self) -> int:
        return len(self._active)

"""WorkflowExecutor —— 执行 Workflow 中的每一步。

职责：
1. 按顺序/并行执行 WorkflowPlan 中的步骤
2. 每步调用 Agent Runtime 或 Tool Runtime
3. 管理重试
4. 保存 Checkpoint
5. 发布事件

WorkflowExecutor 不直接调用 Provider / MCP / Database。
只依赖 Agent Runtime、Tool Runtime、Memory、Knowledge、EventBus。
"""

from __future__ import annotations
import time
from typing import Any

from core.workflow.models import (
    WorkflowPlan, WorkflowStep, WorkflowResult, WorkflowStatus,
    WorkflowRequest, WorkflowCheckpoint, StepStatus, StepType,
)
from core.workflow.state import WorkflowStateMachine
from core.workflow.checkpoint import CheckpointManager
from core.workflow.events import publish_workflow_event, WorkflowEventTypes
from core.workflow.exceptions import StepExecutionError
from core.workflow.config import WorkflowConfig


class WorkflowExecutor:
    """Workflow 步骤执行器"""

    def __init__(
        self,
        agent_runtime=None,
        tool_executor=None,
        memory_manager=None,
        knowledge_manager=None,
        checkpoint_mgr: CheckpointManager | None = None,
        config: WorkflowConfig | None = None,
        bus=None,
    ):
        self._agent = agent_runtime
        self._tool_executor = tool_executor
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._checkpoint_mgr = checkpoint_mgr or CheckpointManager()
        self._config = config or WorkflowConfig()
        self._bus = bus

    async def execute(self, plan: WorkflowPlan, request: WorkflowRequest) -> WorkflowResult:
        """执行完整的 Workflow Plan"""
        state = WorkflowStateMachine(WorkflowStatus.RUNNING)
        t0 = time.time()
        completed = 0
        failed = 0
        outputs: dict[str, Any] = {}
        errors: list[str] = []

        for i, step in enumerate(plan.steps):
            # 检查是否有快照可跳过已完成的步骤
            if step.id in outputs:
                continue

            await publish_workflow_event(
                self._bus, WorkflowEventTypes.STEP_STARTED,
                plan.workflow_id, request.agent_id, request.session_id,
                {"step_name": step.name, "step_index": i},
            )

            try:
                result = await self._execute_step(step, request)
                step.status = StepStatus.COMPLETED
                step.result = result
                outputs[step.id] = result
                completed += 1

                await publish_workflow_event(
                    self._bus, WorkflowEventTypes.STEP_COMPLETED,
                    plan.workflow_id, request.agent_id, request.session_id,
                    {"step_name": step.name, "step_index": i},
                )
            except StepExecutionError as e:
                step.status = StepStatus.FAILED
                step.error = str(e)
                errors.append(f"Step {step.name}: {e}")
                failed += 1

                await publish_workflow_event(
                    self._bus, WorkflowEventTypes.STEP_FAILED,
                    plan.workflow_id, request.agent_id, request.session_id,
                    {"step_name": step.name, "error": str(e)},
                )

                # 重试逻辑
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    await publish_workflow_event(
                        self._bus, WorkflowEventTypes.RETRY,
                        plan.workflow_id, request.agent_id, request.session_id,
                        {"step_name": step.name, "retry": step.retry_count},
                    )
                    try:
                        result = await self._execute_step(step, request)
                        step.status = StepStatus.COMPLETED
                        step.result = result
                        outputs[step.id] = result
                        completed += 1
                        failed -= 1
                        errors.pop()
                    except Exception:
                        pass  # 重试失败，保持 failed

            # 保存 checkpoint
            if self._config.checkpoint_enabled:
                self._checkpoint_mgr.save(WorkflowCheckpoint(
                    workflow_id=plan.workflow_id,
                    status=WorkflowStatus.RUNNING,
                    current_step_index=i + 1,
                    completed_step_ids=[s.id for s in plan.steps[:i+1] if s.status == StepStatus.COMPLETED],
                    variables=request.variables,
                    step_outputs=outputs,
                    retry_counts={s.id: s.retry_count for s in plan.steps},
                ))

        total_ms = (time.time() - t0) * 1000
        final_status = WorkflowStatus.COMPLETED if failed == 0 else WorkflowStatus.FAILED

        return WorkflowResult(
            workflow_id=plan.workflow_id,
            status=final_status,
            steps_completed=completed,
            steps_failed=failed,
            total_latency_ms=total_ms,
            outputs=outputs,
            errors=errors,
        )

    async def _execute_step(self, step: WorkflowStep, request: WorkflowRequest) -> Any:
        """执行单个步骤 —— 委托给 Agent Runtime 或 Tool Runtime"""
        if step.step_type == StepType.AGENT_CALL:
            return await self._execute_agent_step(step, request)
        elif step.step_type == StepType.TOOL_CALL:
            return await self._execute_tool_step(step, request)
        elif step.step_type == StepType.WAIT:
            import asyncio
            await asyncio.sleep(step.arguments.get("seconds", 1))
            return {"waited": step.arguments.get("seconds", 1)}
        else:
            raise StepExecutionError(f"Unknown step type: {step.step_type}")

    async def _execute_agent_step(self, step: WorkflowStep, request: WorkflowRequest) -> Any:
        """调用 Agent Runtime"""
        if self._agent is None:
            raise StepExecutionError("Agent Runtime not configured")

        from core.agents.models import AgentRequest
        agent_req = AgentRequest(
            user_input=step.arguments.get("prompt", request.user_input),
            session_id=request.session_id,
            agent_id=step.agent_name or request.agent_id,
            memory_enabled=self._config.memory_enabled,
            knowledge_enabled=self._config.knowledge_enabled,
            tools_enabled=bool(step.arguments.get("tools", [])),
            trace_id=request.trace_id,
        )
        response = await self._agent.run(agent_req)
        return {"answer": response.answer, "tool_calls": [tc.dict() for tc in response.tool_calls]}

    async def _execute_tool_step(self, step: WorkflowStep, request: WorkflowRequest) -> Any:
        """调用 Tool Runtime"""
        if self._tool_executor is None:
            raise StepExecutionError("Tool Executor not configured")

        from core.tools.models import ToolRequest
        tool_req = ToolRequest(
            tool_name=step.tool_name,
            arguments=step.arguments,
            session_id=request.session_id,
            agent_id=request.agent_id,
            trace_id=request.trace_id,
        )
        result = await self._tool_executor.execute(tool_req)
        if not result.success:
            raise StepExecutionError(result.error or "Tool execution failed")
        return result.output

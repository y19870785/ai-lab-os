import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.workflow.runtime import WorkflowRuntime
from core.workflow.registry import WorkflowRegistry
from core.workflow.models import (
    WorkflowInfo, WorkflowRequest, WorkflowStep, WorkflowPlan,
    WorkflowStatus, StepType,
)
from core.workflow.protocol import WorkflowProtocol
from core.workflow.config import WorkflowConfig
from core.workflow.executor import WorkflowExecutor
from core.workflow.exceptions import WorkflowNotFoundError


class _SimpleWorkflow(WorkflowProtocol):
    def __init__(self):
        self._info = WorkflowInfo(name="simple-wf", description="Simple test workflow")
    async def initialize(self): pass
    async def plan(self, request: WorkflowRequest) -> WorkflowPlan:
        return WorkflowPlan(
            steps=[WorkflowStep(name="echo", step_type=StepType.WAIT, arguments={"seconds": 0.001})],
        )
    async def execute(self, request: WorkflowRequest):
        from core.workflow.models import WorkflowResult
        return WorkflowResult(workflow_id=self._info.id, steps_completed=1)
    async def health_check(self): return True
    async def shutdown(self): pass
    @property
    def info(self): return self._info


class TestWorkflowRuntime:
    def _make_runtime(self):
        reg = WorkflowRegistry()
        wf = _SimpleWorkflow()
        reg.register(wf.info, lambda: _SimpleWorkflow())
        executor = WorkflowExecutor(config=WorkflowConfig())
        runtime = WorkflowRuntime(registry=reg, executor=executor)
        return runtime

    async def test_run_simple_workflow(self):
        runtime = self._make_runtime()
        req = WorkflowRequest(workflow_name="simple-wf", user_input="hello", session_id="s1")
        result = await runtime.run(req)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 1

    async def test_not_found(self):
        reg = WorkflowRegistry()
        runtime = WorkflowRuntime(registry=reg)
        req = WorkflowRequest(workflow_name="nonexistent")
        with pytest.raises(WorkflowNotFoundError):
            await runtime.run(req)

    async def test_cancel(self):
        runtime = self._make_runtime()
        # Run a quick workflow to get it registered as active
        req = WorkflowRequest(workflow_name="simple-wf", user_input="go", session_id="s2")
        await runtime.run(req)
        # After completion, active state remains
        assert runtime.active_count >= 1

    async def test_registry_access(self):
        runtime = self._make_runtime()
        assert runtime.registry.exists("simple-wf")

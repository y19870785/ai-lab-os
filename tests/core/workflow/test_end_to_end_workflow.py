import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.workflow.runtime import WorkflowRuntime
from core.workflow.registry import WorkflowRegistry
from core.workflow.executor import WorkflowExecutor
from core.workflow.models import (
    WorkflowInfo, WorkflowRequest, WorkflowStep, WorkflowPlan,
    WorkflowStatus, StepType,
)
from core.workflow.protocol import WorkflowProtocol
from core.workflow.config import WorkflowConfig


class _MultiStepWorkflow(WorkflowProtocol):
    """A workflow that simulates: analyze -> calculate -> summarize"""
    def __init__(self):
        self._info = WorkflowInfo(name="e2e-wf", description="E2E test", tags=["test"])
    async def initialize(self): pass
    async def plan(self, request: WorkflowRequest) -> WorkflowPlan:
        return WorkflowPlan(
            steps=[
                WorkflowStep(name="wait-1", step_type=StepType.WAIT, arguments={"seconds": 0.001}),
                WorkflowStep(name="wait-2", step_type=StepType.WAIT, arguments={"seconds": 0.001}),
                WorkflowStep(name="wait-3", step_type=StepType.WAIT, arguments={"seconds": 0.001}),
            ],
        )
    async def execute(self, request: WorkflowRequest):
        from core.workflow.models import WorkflowResult
        return WorkflowResult(workflow_id=self._info.id, status=WorkflowStatus.COMPLETED, steps_completed=3)
    async def health_check(self): return True
    async def shutdown(self): pass
    @property
    def info(self): return self._info


class TestEndToEndWorkflow:
    async def test_multi_step_workflow(self):
        reg = WorkflowRegistry()
        wf = _MultiStepWorkflow()
        reg.register(wf.info, lambda: _MultiStepWorkflow())
        executor = WorkflowExecutor(config=WorkflowConfig())
        runtime = WorkflowRuntime(registry=reg, executor=executor)
        req = WorkflowRequest(workflow_name="e2e-wf", user_input="run pipeline", session_id="e2e-s1")
        result = await runtime.run(req)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 3
        assert result.steps_failed == 0

    async def test_workflow_with_variables(self):
        reg = WorkflowRegistry()
        wf = _MultiStepWorkflow()
        reg.register(wf.info, lambda: _MultiStepWorkflow())
        executor = WorkflowExecutor(config=WorkflowConfig())
        runtime = WorkflowRuntime(registry=reg, executor=executor)
        req = WorkflowRequest(
            workflow_name="e2e-wf",
            user_input="run with vars",
            session_id="e2e-vars",
            variables={"priority": "high", "source": "api"},
        )
        result = await runtime.run(req)
        assert result.status == WorkflowStatus.COMPLETED

    async def test_workflow_registry_search(self):
        reg = WorkflowRegistry()
        wf = _MultiStepWorkflow()
        reg.register(wf.info, lambda: _MultiStepWorkflow())
        results = reg.search(tag="test")
        assert len(results) == 1
        assert results[0].name == "e2e-wf"

    async def test_checkpoint_after_completion(self):
        reg = WorkflowRegistry()
        wf = _MultiStepWorkflow()
        reg.register(wf.info, lambda: _MultiStepWorkflow())
        executor = WorkflowExecutor(config=WorkflowConfig())
        runtime = WorkflowRuntime(registry=reg, executor=executor)
        req = WorkflowRequest(workflow_name="e2e-wf", user_input="go")
        result = await runtime.run(req)
        assert result.status == WorkflowStatus.COMPLETED
        # Checkpoint should exist
        assert executor._checkpoint_mgr.exists(wf.info.id)

    async def test_multiple_workflow_registrations(self):
        reg = WorkflowRegistry()
        for i in range(5):
            info = WorkflowInfo(name=f"wf-{i}", tags=[f"tag-{i}"])
            reg.register(info, lambda: None)
        assert reg.count == 5
        assert all(reg.exists(f"wf-{i}") for i in range(5))

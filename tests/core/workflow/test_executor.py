import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.workflow.executor import WorkflowExecutor
from core.workflow.models import (
    WorkflowPlan, WorkflowStep, WorkflowRequest, WorkflowResult,
    WorkflowStatus, StepType, StepStatus,
)
from core.workflow.config import WorkflowConfig


class FakeAgentRuntime:
    async def initialize(self): pass
    async def shutdown(self): pass
    async def run(self, request):
        from core.agents.models import AgentResponse
        return AgentResponse(answer=f"Processed: {request.user_input}")
    async def build_context(self, request): pass
    async def invoke_llm(self, context): return ""
    async def invoke_tools(self, names, context): return {}
    async def after_response(self, req, resp): pass
    @property
    def info(self):
        from core.agents.models import AgentInfo
        return AgentInfo(name="fake")


class TestWorkflowExecutor:
    def _make_executor(self):
        return WorkflowExecutor(
            agent_runtime=FakeAgentRuntime(),
            config=WorkflowConfig(),
        )

    async def test_single_agent_step(self):
        executor = self._make_executor()
        plan = WorkflowPlan(
            workflow_id="wf-1",
            steps=[WorkflowStep(name="analyze", step_type=StepType.AGENT_CALL,
                                agent_name="analyst",
                                arguments={"prompt": "Analyze data"})],
        )
        req = WorkflowRequest(workflow_name="test", user_input="go", session_id="s1")
        result = await executor.execute(plan, req)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 1
        assert result.steps_failed == 0
        assert len(result.outputs) == 1

    async def test_multiple_steps(self):
        executor = self._make_executor()
        plan = WorkflowPlan(
            workflow_id="wf-2",
            steps=[
                WorkflowStep(name="s1", step_type=StepType.AGENT_CALL, agent_name="a",
                             arguments={"prompt": "step1"}),
                WorkflowStep(name="s2", step_type=StepType.AGENT_CALL, agent_name="a",
                             arguments={"prompt": "step2"}),
                WorkflowStep(name="s3", step_type=StepType.AGENT_CALL, agent_name="a",
                             arguments={"prompt": "step3"}),
            ],
        )
        req = WorkflowRequest(workflow_name="multi", user_input="go")
        result = await executor.execute(plan, req)
        assert result.steps_completed == 3
        assert result.steps_failed == 0

    async def test_tool_step(self):
        class FakeToolExecutor:
            async def execute(self, req):
                from core.tools.models import ToolResult
                return ToolResult(success=True, output=f"Tool: {req.tool_name}")
        executor = WorkflowExecutor(tool_executor=FakeToolExecutor(), config=WorkflowConfig())
        plan = WorkflowPlan(
            workflow_id="wf-tool",
            steps=[WorkflowStep(name="calc", step_type=StepType.TOOL_CALL,
                                tool_name="calculator",
                                arguments={"expression": "2+2"})],
        )
        req = WorkflowRequest(workflow_name="tool-test")
        result = await executor.execute(plan, req)
        assert result.steps_completed == 1

    async def test_tool_step_failure(self):
        class FailingToolExecutor:
            async def execute(self, req):
                from core.tools.models import ToolResult
                return ToolResult(success=False, error="Tool error")
        executor = WorkflowExecutor(tool_executor=FailingToolExecutor(), config=WorkflowConfig())
        plan = WorkflowPlan(
            workflow_id="wf-fail",
            steps=[WorkflowStep(name="bad-tool", step_type=StepType.TOOL_CALL,
                                tool_name="doesnt-exist")],
        )
        req = WorkflowRequest(workflow_name="fail-test")
        result = await executor.execute(plan, req)
        assert result.steps_failed == 1

    async def test_wait_step(self):
        executor = self._make_executor()
        plan = WorkflowPlan(
            workflow_id="wf-wait",
            steps=[WorkflowStep(name="delay", step_type=StepType.WAIT,
                                arguments={"seconds": 0.01})],
        )
        req = WorkflowRequest(workflow_name="wait-test")
        result = await executor.execute(plan, req)
        assert result.steps_completed == 1

    async def test_checkpoint_saved(self):
        executor = self._make_executor()
        plan = WorkflowPlan(
            workflow_id="wf-cp",
            steps=[
                WorkflowStep(name="s1", step_type=StepType.AGENT_CALL, agent_name="x",
                             arguments={"prompt": "hi"}),
                WorkflowStep(name="s2", step_type=StepType.AGENT_CALL, agent_name="x",
                             arguments={"prompt": "hi"}),
            ],
        )
        req = WorkflowRequest(workflow_name="cp-test")
        await executor.execute(plan, req)
        assert executor._checkpoint_mgr.exists("wf-cp")
        cp = executor._checkpoint_mgr.load("wf-cp")
        assert cp is not None
        assert cp.current_step_index == 2

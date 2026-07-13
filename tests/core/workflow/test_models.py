import pytest
from core.workflow.models import (
    WorkflowInfo, WorkflowStep, WorkflowPlan, WorkflowRequest,
    WorkflowResult, WorkflowCheckpoint, WorkflowStatus, StepStatus, StepType,
)

class TestWorkflowModels:
    def test_workflow_info(self):
        info = WorkflowInfo(name="test-wf", description="A test workflow")
        assert info.name == "test-wf"
        assert info.version == "1.0.0"
        assert len(info.id) > 0

    def test_workflow_step(self):
        step = WorkflowStep(name="step1", step_type=StepType.AGENT_CALL, agent_name="analyst")
        assert step.step_type == StepType.AGENT_CALL
        assert step.status == StepStatus.PENDING
        assert step.max_retries == 1

    def test_workflow_plan(self):
        steps = [WorkflowStep(name="s1"), WorkflowStep(name="s2")]
        plan = WorkflowPlan(workflow_id="wf-1", steps=steps, estimated_steps=2)
        assert len(plan.steps) == 2
        assert plan.estimated_steps == 2

    def test_workflow_request(self):
        req = WorkflowRequest(workflow_name="test", user_input="hello", session_id="s1")
        assert req.workflow_name == "test"
        assert req.user_input == "hello"

    def test_workflow_result(self):
        result = WorkflowResult(workflow_id="wf-1", steps_completed=3, steps_failed=0)
        assert result.status == WorkflowStatus.COMPLETED
        assert result.steps_completed == 3

    def test_workflow_checkpoint(self):
        cp = WorkflowCheckpoint(workflow_id="wf-1", current_step_index=2,
                                completed_step_ids=["s1"], variables={"key": "val"})
        assert cp.current_step_index == 2
        assert cp.variables["key"] == "val"

    def test_status_enum(self):
        assert WorkflowStatus.CREATED.value == "created"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"

    def test_step_type_enum(self):
        assert StepType.AGENT_CALL.value == "agent_call"
        assert StepType.TOOL_CALL.value == "tool_call"

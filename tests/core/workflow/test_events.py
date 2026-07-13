import pytest
from core.workflow.events import WorkflowEventTypes


class TestWorkflowEvents:
    def test_event_type_constants(self):
        assert WorkflowEventTypes.CREATED == "workflow.created"
        assert WorkflowEventTypes.STARTED == "workflow.started"
        assert WorkflowEventTypes.COMPLETED == "workflow.completed"
        assert WorkflowEventTypes.FAILED == "workflow.failed"
        assert WorkflowEventTypes.PAUSED == "workflow.paused"
        assert WorkflowEventTypes.RETRY == "workflow.retry"
        assert WorkflowEventTypes.CHECKPOINT == "workflow.checkpoint"
        assert WorkflowEventTypes.STEP_STARTED == "workflow.step.started"
        assert WorkflowEventTypes.STEP_COMPLETED == "workflow.step.completed"
        assert WorkflowEventTypes.STEP_FAILED == "workflow.step.failed"

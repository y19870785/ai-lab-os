import pytest
from core.workflow.state import WorkflowStateMachine
from core.workflow.models import WorkflowStatus
from core.workflow.exceptions import WorkflowStateError


class TestWorkflowStateMachine:
    def test_initial_state(self):
        sm = WorkflowStateMachine()
        assert sm.current == WorkflowStatus.CREATED

    def test_valid_transition(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        assert sm.current == WorkflowStatus.READY

    def test_invalid_transition(self):
        sm = WorkflowStateMachine()
        with pytest.raises(WorkflowStateError):
            sm.transition(WorkflowStatus.RUNNING)  # CREATED -> RUNNING is invalid

    def test_full_happy_path(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        sm.transition(WorkflowStatus.PLANNING)
        sm.transition(WorkflowStatus.RUNNING)
        sm.transition(WorkflowStatus.COMPLETED)
        assert sm.current == WorkflowStatus.COMPLETED
        assert sm.is_terminal()

    def test_failure_path(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        sm.transition(WorkflowStatus.PLANNING)
        sm.transition(WorkflowStatus.RUNNING)
        sm.transition(WorkflowStatus.FAILED)
        assert sm.current == WorkflowStatus.FAILED

    def test_pause_resume(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        sm.transition(WorkflowStatus.PLANNING)
        sm.transition(WorkflowStatus.RUNNING)
        sm.transition(WorkflowStatus.PAUSED)
        sm.transition(WorkflowStatus.RESUMED)
        sm.transition(WorkflowStatus.RUNNING)
        assert sm.current == WorkflowStatus.RUNNING

    def test_can_transition(self):
        sm = WorkflowStateMachine()
        assert sm.can_transition(WorkflowStatus.READY) is True
        assert sm.can_transition(WorkflowStatus.RUNNING) is False

    def test_is_runnable(self):
        sm = WorkflowStateMachine()
        assert sm.is_runnable() is False
        sm.transition(WorkflowStatus.READY)
        assert sm.is_runnable() is True

    def test_reset(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        sm.transition(WorkflowStatus.PLANNING)
        sm.reset()
        assert sm.current == WorkflowStatus.CREATED

    def test_retry_from_failed(self):
        sm = WorkflowStateMachine()
        sm.transition(WorkflowStatus.READY)
        sm.transition(WorkflowStatus.PLANNING)
        sm.transition(WorkflowStatus.RUNNING)
        sm.transition(WorkflowStatus.FAILED)
        sm.transition(WorkflowStatus.RETRYING)
        sm.transition(WorkflowStatus.RUNNING)
        assert sm.current == WorkflowStatus.RUNNING

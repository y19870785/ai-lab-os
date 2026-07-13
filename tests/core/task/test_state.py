import pytest
from core.task.state import TaskStateMachine
from core.task.models import TaskStatus
from core.task.exceptions import TaskStateError

class TestTaskStateMachine:
    def test_happy_path(self):
        sm = TaskStateMachine()
        sm.transition(TaskStatus.READY)
        sm.transition(TaskStatus.RUNNING)
        sm.transition(TaskStatus.COMPLETED)
        assert sm.current == TaskStatus.COMPLETED

    def test_invalid(self):
        sm = TaskStateMachine()
        with pytest.raises(TaskStateError):
            sm.transition(TaskStatus.RUNNING)

    def test_pause_resume(self):
        sm = TaskStateMachine()
        sm.transition(TaskStatus.READY)
        sm.transition(TaskStatus.RUNNING)
        sm.transition(TaskStatus.PAUSED)
        sm.transition(TaskStatus.RUNNING)
        assert sm.current == TaskStatus.RUNNING

    def test_retry_from_failed(self):
        sm = TaskStateMachine()
        sm.transition(TaskStatus.READY)
        sm.transition(TaskStatus.RUNNING)
        sm.transition(TaskStatus.FAILED)
        sm.transition(TaskStatus.RETRYING)
        sm.transition(TaskStatus.RUNNING)
        assert sm.current == TaskStatus.RUNNING

    def test_terminal(self):
        sm = TaskStateMachine()
        sm.transition(TaskStatus.READY)
        sm.transition(TaskStatus.RUNNING)
        sm.transition(TaskStatus.COMPLETED)
        assert sm.is_terminal()

    def test_can_transition(self):
        sm = TaskStateMachine()
        assert sm.can_transition(TaskStatus.READY)
        assert not sm.can_transition(TaskStatus.COMPLETED)

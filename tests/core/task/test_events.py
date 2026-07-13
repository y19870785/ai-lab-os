import pytest
from core.task.events import TaskEventTypes

class TestTaskEvents:
    def test_all_event_constants(self):
        assert TaskEventTypes.CREATED == "task.created"
        assert TaskEventTypes.STARTED == "task.started"
        assert TaskEventTypes.RUNNING == "task.running"
        assert TaskEventTypes.PAUSED == "task.paused"
        assert TaskEventTypes.RESUMED == "task.resumed"
        assert TaskEventTypes.WAITING == "task.waiting"
        assert TaskEventTypes.RETRY == "task.retry"
        assert TaskEventTypes.COMPLETED == "task.completed"
        assert TaskEventTypes.FAILED == "task.failed"
        assert TaskEventTypes.CANCELLED == "task.cancelled"
        assert TaskEventTypes.DESTROYED == "task.destroyed"
        assert TaskEventTypes.TIMEOUT == "task.timeout"

import pytest
from core.scheduler.events import SchedulerEventTypes


class TestSchedulerEvents:
    def test_event_type_constants(self):
        assert SchedulerEventTypes.CREATED == "scheduler.created"
        assert SchedulerEventTypes.STARTED == "scheduler.started"
        assert SchedulerEventTypes.JOB_STARTED == "scheduler.job.started"
        assert SchedulerEventTypes.JOB_COMPLETED == "scheduler.job.completed"
        assert SchedulerEventTypes.JOB_FAILED == "scheduler.job.failed"
        assert SchedulerEventTypes.PAUSED == "scheduler.paused"
        assert SchedulerEventTypes.RESUMED == "scheduler.resumed"
        assert SchedulerEventTypes.DELETED == "scheduler.deleted"
        assert SchedulerEventTypes.SHUTDOWN == "scheduler.shutdown"

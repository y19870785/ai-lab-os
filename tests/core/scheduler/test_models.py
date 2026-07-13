import pytest
from datetime import datetime, timezone, timedelta
from core.scheduler.models import (
    Job, JobInfo, JobRun, JobStatus, JobRunStatus,
    Trigger, TriggerType, ScheduleRequest,
)

class TestSchedulerModels:
    def test_job_info_defaults(self):
        info = JobInfo(name="test-job")
        assert info.name == "test-job"
        assert info.version == "1.0.0"
        assert len(info.id) > 0

    def test_trigger_cron(self):
        t = Trigger(trigger_type=TriggerType.CRON, cron_expression="*/5 * * * *")
        assert t.trigger_type == TriggerType.CRON
        assert t.cron_expression == "*/5 * * * *"

    def test_trigger_interval(self):
        t = Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60)
        assert t.interval_seconds == 60

    def test_trigger_one_shot(self):
        dt = datetime.now(timezone.utc) + timedelta(hours=1)
        t = Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=dt)
        assert t.run_at == dt

    def test_job_defaults(self):
        job = Job(info=JobInfo(name="j1"), workflow_name="test-wf")
        assert job.status == JobStatus.ACTIVE
        assert job.max_retries == 3
        assert job.timeout == 300
        assert job.run_count == 0

    def test_job_run(self):
        run = JobRun(job_id="j1", job_name="test")
        assert run.status == JobRunStatus.RUNNING
        assert run.started_at is not None

    def test_schedule_request(self):
        req = ScheduleRequest(
            job_name="daily-report",
            workflow_name="report-wf",
            trigger=Trigger(trigger_type=TriggerType.CRON, cron_expression="0 9 * * *"),
        )
        assert req.job_name == "daily-report"
        assert req.workflow_name == "report-wf"

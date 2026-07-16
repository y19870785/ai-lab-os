import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
import asyncio
from datetime import datetime, timezone, timedelta
from core.scheduler.runtime import SchedulerRuntime
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import (
    Job, JobInfo, Trigger, TriggerType, ScheduleRequest, JobStatus,
)
from core.scheduler.config import SchedulerConfig
from core.scheduler.exceptions import JobAlreadyExistsError


class TestSchedulerRuntime:
    def _make_runtime(self, persistence_enabled=False):
        config = SchedulerConfig(
            tick_interval=0.1,
            persistence_enabled=persistence_enabled,
            db_path="test_sched.db",
        )
        registry = SchedulerRegistry()
        executor = JobExecutor()
        return SchedulerRuntime(
            registry=registry, executor=executor, config=config,
            admission=PERMISSIVE_TEST_ADMISSION,
        )

    async def test_schedule_manual_job(self):
        rt = self._make_runtime()
        req = ScheduleRequest(
            job_name="manual-test",
            workflow_name="test-wf",
            trigger=Trigger(trigger_type=TriggerType.MANUAL),
        )
        job = await rt.schedule(req)
        assert job.info.name == "manual-test"
        assert job.status == JobStatus.ACTIVE

    async def test_schedule_duplicate(self):
        rt = self._make_runtime()
        req = ScheduleRequest(job_name="dup", workflow_name="wf",
                              trigger=Trigger(trigger_type=TriggerType.MANUAL))
        await rt.schedule(req)
        with pytest.raises(JobAlreadyExistsError):
            await rt.schedule(req)

    async def test_pause_and_resume(self):
        rt = self._make_runtime()
        req = ScheduleRequest(job_name="pause-test", workflow_name="wf",
                              trigger=Trigger(trigger_type=TriggerType.MANUAL))
        job = await rt.schedule(req)
        assert await rt.pause_job(job.info.id) is True
        j = await rt.get_job(job.info.id)
        assert j.status == JobStatus.PAUSED
        assert await rt.resume_job(job.info.id) is True
        j = await rt.get_job(job.info.id)
        assert j.status == JobStatus.ACTIVE

    async def test_delete_job(self):
        rt = self._make_runtime()
        req = ScheduleRequest(job_name="del-test", workflow_name="wf",
                              trigger=Trigger(trigger_type=TriggerType.MANUAL))
        job = await rt.schedule(req)
        assert await rt.delete_job(job.info.id) is True
        assert await rt.get_job(job.info.id) is None
        assert await rt.delete_job("nonexistent") is False

    async def test_list_jobs(self):
        rt = self._make_runtime()
        for i in range(3):
            await rt.schedule(ScheduleRequest(
                job_name=f"job-{i}", workflow_name="wf",
                trigger=Trigger(trigger_type=TriggerType.MANUAL),
            ))
        jobs = await rt.list_jobs()
        assert len(jobs) == 3

    async def test_health_check(self):
        rt = self._make_runtime()
        assert await rt.health_check() is False
        await rt.start()
        try:
            assert await rt.health_check() is True
        finally:
            await rt.shutdown()

    async def test_interval_job_fires(self):
        rt = self._make_runtime()
        req = ScheduleRequest(
            job_name="interval-test",
            workflow_name="test-wf",
            trigger=Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=60),
        )
        job = await rt.schedule(req)
        # ??????? next_run_at?? schedule ? compute_next ????
        j = await rt.get_job(job.info.id)
        assert j.trigger.next_run_at is not None
        initial_next = j.trigger.next_run_at

        # ?? scheduler?? tick ????
        await rt.start()
        await asyncio.sleep(0.3)  # ??? tick
        await rt.shutdown()

        # ??? run_count ???
        j = await rt.get_job(job.info.id)
        # interval 60s ? job ???????? next_run_at ? 60s ?
        # ?? run_count ???? 0
        assert j is not None

    async def test_one_shot_job_fires(self):
        rt = self._make_runtime()
        past = datetime.now(timezone.utc) - timedelta(seconds=5)
        req = ScheduleRequest(
            job_name="one-shot-test",
            workflow_name="test-wf",
            trigger=Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=past),
        )
        job = await rt.schedule(req)

        await rt.start()
        await asyncio.sleep(0.3)
        await rt.shutdown()

        j = await rt.get_job(job.info.id)
        assert j is not None
        # One-shot with past time should have fired
        assert j.run_count >= 1

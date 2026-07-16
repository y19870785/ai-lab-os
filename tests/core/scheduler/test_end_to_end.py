import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
import asyncio
from datetime import datetime, timezone, timedelta
from core.scheduler.runtime import SchedulerRuntime
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import (
    Trigger, TriggerType, ScheduleRequest, JobStatus, JobRunStatus,
)
from core.scheduler.config import SchedulerConfig


class TestSchedulerEndToEnd:
    """Scheduler ?????? ? ?? ? ?? ? ??"""

    async def test_full_lifecycle(self):
        rt = SchedulerRuntime(
            registry=SchedulerRegistry(),
            executor=JobExecutor(),
            config=SchedulerConfig(tick_interval=0.1, persistence_enabled=False),
            admission=PERMISSIVE_TEST_ADMISSION,
        )

        # ??
        req = ScheduleRequest(
            job_name="e2e-job",
            workflow_name="e2e-wf",
            trigger=Trigger(trigger_type=TriggerType.MANUAL),
        )
        job = await rt.schedule(req)
        assert job.status == JobStatus.ACTIVE

        # ??
        await rt.pause_job(job.info.id)
        j = await rt.get_job(job.info.id)
        assert j.status == JobStatus.PAUSED

        # ??
        await rt.resume_job(job.info.id)
        j = await rt.get_job(job.info.id)
        assert j.status == JobStatus.ACTIVE

        # ??
        assert await rt.delete_job(job.info.id)
        assert await rt.get_job(job.info.id) is None

    async def test_interval_job_multiple_runs(self):
        rt = SchedulerRuntime(
            registry=SchedulerRegistry(),
            executor=JobExecutor(),
            config=SchedulerConfig(tick_interval=0.1, persistence_enabled=False),
            admission=PERMISSIVE_TEST_ADMISSION,
        )

        # ????????? one-shot job?????
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        req = ScheduleRequest(
            job_name="fast-job",
            workflow_name="test-wf",
            trigger=Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=past),
        )
        job = await rt.schedule(req)

        await rt.start()
        await asyncio.sleep(0.3)
        await rt.shutdown()

        j = await rt.get_job(job.info.id)
        assert j is not None
        assert j.run_count >= 1

    async def test_multiple_jobs(self):
        rt = SchedulerRuntime(
            registry=SchedulerRegistry(),
            executor=JobExecutor(),
            config=SchedulerConfig(tick_interval=0.1, persistence_enabled=False),
            admission=PERMISSIVE_TEST_ADMISSION,
        )

        for i in range(5):
            await rt.schedule(ScheduleRequest(
                job_name=f"multi-{i}", workflow_name="wf",
                trigger=Trigger(trigger_type=TriggerType.MANUAL),
            ))

        jobs = await rt.list_jobs()
        assert len(jobs) == 5

    async def test_concurrent_limit(self):
        config = SchedulerConfig(tick_interval=0.1, max_concurrent_jobs=1, persistence_enabled=False)
        rt = SchedulerRuntime(
            registry=SchedulerRegistry(), executor=JobExecutor(), config=config,
            admission=PERMISSIVE_TEST_ADMISSION,
        )

        # ???? past one-shot jobs
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        for i in range(2):
            await rt.schedule(ScheduleRequest(
                job_name=f"concurrent-{i}", workflow_name="wf",
                trigger=Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=past),
            ))

        await rt.start()
        await asyncio.sleep(0.3)
        await rt.shutdown()

        # ???? job ?????
        jobs = await rt.list_jobs()
        total_runs = sum(j.run_count for j in jobs)
        assert total_runs >= 1

import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import Job, JobInfo, Trigger, TriggerType, JobStatus, JobRunStatus


class TestJobExecutor:
    async def test_execute_without_workflow(self):
        executor = JobExecutor(workflow_runtime=None)
        job = Job(info=JobInfo(name="test"), workflow_name="dummy",
                  trigger=Trigger(trigger_type=TriggerType.MANUAL))
        run = await executor.execute(job)
        assert run.status == JobRunStatus.SUCCESS
        assert job.run_count == 1

    async def test_execute_paused_job(self):
        from core.scheduler.exceptions import JobStateError
        executor = JobExecutor()
        job = Job(info=JobInfo(name="paused"), status=JobStatus.PAUSED)
        with pytest.raises(JobStateError):
            await executor.execute(job)

    async def test_execute_timeout(self):
        class SlowWorkflowRuntime:
            async def run(self, req):
                import asyncio
                await asyncio.sleep(10)

        executor = JobExecutor(workflow_runtime=SlowWorkflowRuntime())
        job = Job(info=JobInfo(name="slow"), workflow_name="slow-wf", timeout=1,
                  trigger=Trigger(trigger_type=TriggerType.MANUAL))
        run = await executor.execute(job)
        assert run.status == JobRunStatus.TIMEOUT

    async def test_execute_updates_job(self):
        executor = JobExecutor()
        job = Job(info=JobInfo(name="counter"), workflow_name="dummy")
        assert job.run_count == 0
        await executor.execute(job)
        assert job.run_count == 1
        assert job.last_run_at is not None

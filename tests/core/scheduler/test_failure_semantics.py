import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.bus.bus import MemoryBus
from core.scheduler.config import SchedulerConfig
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import (
    JobRun,
    JobRunStatus,
    ScheduleRequest,
    Trigger,
    TriggerType,
)
from core.scheduler.runtime import SchedulerRuntime
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_tick_failure_is_observable_in_health_log_and_event(monkeypatch, caplog):
    bus = MemoryBus()
    events = []

    async def collect(event):
        events.append(event)

    async def broken_tick():
        raise RuntimeError("tick storage failed")

    await bus.start()
    await bus.subscribe("scheduler.tick.failed", collect)
    runtime = SchedulerRuntime(
        config=SchedulerConfig(tick_interval=0.01, failure_threshold=2),
        bus=bus,
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    monkeypatch.setattr(runtime, "_tick", broken_tick)
    try:
        await runtime.start()
        await asyncio.sleep(0.05)
        health = await runtime.health()
        assert health["status"] == "failed"
        assert health["consecutive_failures"] >= 2
        assert health["last_error"]["code"] == "scheduler.tick.failed"
        assert events
        assert events[0].payload["code"] == "scheduler.tick.failed"
        assert "scheduler.tick.failed" in caplog.text
    finally:
        await runtime.shutdown()
        await bus.stop()


class BlockingJobExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = False

    async def execute(self, job):
        self.started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return JobRun(
            job_id=job.info.id,
            job_name=job.info.name,
            status=JobRunStatus.SUCCESS,
            trace_id="job-trace",
        )


async def _schedule_due_job(runtime):
    return await runtime.schedule(ScheduleRequest(
        job_name="due-job",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))


async def test_background_job_is_tracked_and_removed_after_completion():
    executor = BlockingJobExecutor()
    runtime = SchedulerRuntime(executor=executor, admission=PERMISSIVE_TEST_ADMISSION)
    await _schedule_due_job(runtime)

    await runtime._tick()
    await executor.started.wait()
    assert len(runtime._background_tasks) == 1

    executor.release.set()
    await asyncio.gather(*list(runtime._background_tasks))
    await asyncio.sleep(0)
    assert runtime._background_tasks == set()


async def test_shutdown_cancels_and_collects_running_job_tasks():
    executor = BlockingJobExecutor()
    runtime = SchedulerRuntime(
        executor=executor,
        config=SchedulerConfig(cancel_running_jobs_on_shutdown=True, shutdown_timeout=0.2),
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    await _schedule_due_job(runtime)
    await runtime._tick()
    await executor.started.wait()

    await runtime.shutdown()

    assert executor.cancelled is True
    assert runtime._background_tasks == set()


async def test_job_executor_failure_result_has_failure_and_no_success_result():
    executor = JobExecutor(workflow_runtime=None)
    runtime = SchedulerRuntime(executor=executor, admission=PERMISSIVE_TEST_ADMISSION)
    job = await runtime.schedule(ScheduleRequest(
        job_name="missing-runtime",
        workflow_name="workflow",
        trigger=Trigger(trigger_type=TriggerType.MANUAL),
    ))

    run = await executor.execute(job)

    assert run.status == JobRunStatus.FAILED
    assert run.failure is not None
    assert run.failure.code == "scheduler.job.execution_failed"
    assert run.result is None
    assert run.trace_id == run.id

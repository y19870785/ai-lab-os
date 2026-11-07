"""Scheduler trigger calculations must share the injected runtime clock."""

from datetime import UTC, datetime, timedelta

import pytest

from core.scheduler.config import SchedulerConfig
from core.scheduler.models import ScheduleRequest, Trigger, TriggerType
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.runtime import SchedulerRuntime
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from tests.helpers.clock import MutableClock


@pytest.mark.asyncio
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("trigger_type", [TriggerType.INTERVAL, TriggerType.CRON])
@pytest.mark.parametrize("operation", ["schedule", "resume"])
async def test_trigger_uses_runtime_clock(tmp_path, persistent, trigger_type, operation):
    now = datetime(2000, 1, 1, 12, 0, 15, tzinfo=UTC)
    clock = MutableClock(now)
    path = tmp_path / "scheduler.db"
    persistence = SchedulerPersistence(str(path)) if persistent else None
    runtime = SchedulerRuntime(
        config=SchedulerConfig(persistence_enabled=persistent),
        persistence=persistence,
        clock=clock,
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    await runtime.initialize()
    try:
        job = await runtime.schedule(ScheduleRequest(
            job_name="clock-bound", workflow_name="unused",
            trigger=Trigger(
                trigger_type=trigger_type, interval_seconds=60,
                cron_expression="* * * * *",
            ),
        ))
        if operation == "resume":
            await runtime.pause_job(job.info.id)
            now += timedelta(hours=2)
            clock.advance(timedelta(hours=2))
            await runtime.resume_job(job.info.id)
        expected = (
            now + timedelta(seconds=60) if trigger_type == TriggerType.INTERVAL
            else (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
        )
        actual = await runtime.get_job(job.info.id)
        assert actual.trigger.next_run_at == expected
        if persistence is not None:
            stored = await persistence.get_job(job.info.id)
            assert stored.trigger.next_run_at == expected
    finally:
        await runtime.shutdown()

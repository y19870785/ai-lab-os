"""Executable contract for the bounded UTC Cron subset."""

import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from core.scheduler.config import SchedulerConfig
from core.scheduler.exceptions import TriggerError
from core.scheduler.models import JobStatus, ScheduleRequest, Trigger, TriggerType
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.runtime import SchedulerRuntime
from core.scheduler.triggers import TriggerEngine
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION

INVALID = [
    "", "bad", "* * * *", "* * * * * *", "0 9 * * *", "1,2 * * * *",
    "1-5 * * * *", "*/0 * * * *", "*/-1 * * * *", "*/61 * * * *",
    "* */25 * * *", "* */0 * * *", "* * 1 * *", "* * * 1 *",
    "* * * * 1", "*/x * * * *", "*/01 * * * *", "*/５ * * * *",
]


@pytest.mark.parametrize("expression", INVALID)
def test_unsupported_cron_is_rejected_without_calculation(expression):
    trigger = Trigger(trigger_type=TriggerType.CRON, cron_expression=expression)
    assert TriggerEngine.validate(trigger) is False
    assert TriggerEngine.compute_next(trigger, datetime(2000, 1, 1, tzinfo=UTC)) is None


@pytest.mark.parametrize(("expression", "now", "expected"), [
    ("*/5 */2 * * *", "2000-01-01T13:01:00+00:00", "2000-01-01T14:00:00+00:00"),
    ("*/7 * * * *", "2000-01-01T12:56:00+00:00", "2000-01-01T13:00:00+00:00"),
    ("* */5 * * *", "2000-01-01T23:59:59+00:00", "2000-01-02T00:00:00+00:00"),
    ("*/60 */24 * * *", "2000-01-01T00:00:00+00:00", "2000-01-02T00:00:00+00:00"),
    ("*/59 */23 * * *", "2000-01-01T23:59:00+00:00", "2000-01-02T00:00:00+00:00"),
    (" \t*/5  */2 * * * ", "2000-01-01T13:01:00+00:00", "2000-01-01T14:00:00+00:00"),
    ("*/5 * * * *", "2000-01-01T20:03:00+08:00", "2000-01-01T12:05:00+00:00"),
])
def test_cron_returns_earliest_supported_utc_match(expression, now, expected):
    trigger = Trigger(trigger_type=TriggerType.CRON, cron_expression=expression)
    assert TriggerEngine.validate(trigger) is True
    assert TriggerEngine.compute_next(trigger, datetime.fromisoformat(now)) == (
        datetime.fromisoformat(expected)
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("persistent", [False, True])
async def test_invalid_cron_schedule_and_resume_do_not_mutate(tmp_path, persistent):
    path = tmp_path / "scheduler.db"
    persistence = SchedulerPersistence(str(path)) if persistent else None
    runtime = SchedulerRuntime(
        config=SchedulerConfig(persistence_enabled=persistent),
        persistence=persistence, admission=PERMISSIVE_TEST_ADMISSION,
    )
    await runtime.initialize()
    try:
        for expression in INVALID:
            with pytest.raises(TriggerError):
                await runtime.schedule(ScheduleRequest(
                    job_name="invalid", workflow_name="unused",
                    trigger=Trigger(trigger_type=TriggerType.CRON, cron_expression=expression),
                ))
            assert await runtime.list_jobs() == []
        job = await runtime.schedule(ScheduleRequest(
            job_name="legacy", workflow_name="unused",
            trigger=Trigger(trigger_type=TriggerType.CRON, cron_expression="* * * * *"),
        ))
        await runtime.pause_job(job.info.id)
        job = await runtime.get_job(job.info.id)
        job.trigger.cron_expression = "0 9 * * *"
        if persistence:
            # Seed a pre-upgrade stored expression, bypassing current validation.
            with sqlite3.connect(path) as conn:
                conn.execute("UPDATE jobs SET cron_expression=? WHERE id=?",
                             (job.trigger.cron_expression, job.info.id))
        before = job.model_copy(deep=True)
        with pytest.raises(TriggerError):
            await runtime.resume_job(job.info.id)
        after = await runtime.get_job(job.info.id)
        assert after == before
        assert after.status == JobStatus.PAUSED
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("persistent", [False, True])
async def test_tick_rejects_legacy_cron_before_any_dispatch(tmp_path, persistent):
    path = tmp_path / "scheduler.db"
    persistence = SchedulerPersistence(str(path)) if persistent else None
    config = SchedulerConfig(persistence_enabled=persistent)
    runtime = SchedulerRuntime(config=config, persistence=persistence,
                               admission=PERMISSIVE_TEST_ADMISSION)
    await runtime.initialize()
    try:
        for index in range(2):
            job = await runtime.schedule(ScheduleRequest(
                job_name=f"legacy-{index}", workflow_name="unused",
                trigger=Trigger(trigger_type=TriggerType.CRON, cron_expression="* * * * *"),
            ))
            job.trigger.next_run_at = datetime(2000, 1, 1, tzinfo=UTC)
            if index == 1:
                job.trigger.cron_expression = "0 9 * * *"
            if persistence:
                with sqlite3.connect(path) as conn:
                    conn.execute("UPDATE jobs SET cron_expression=?, next_run_at=? WHERE id=?",
                                 (job.trigger.cron_expression,
                                  job.trigger.next_run_at.isoformat(), job.info.id))
        if persistent:
            await runtime.shutdown()
            runtime = SchedulerRuntime(
                config=config, persistence=SchedulerPersistence(str(path)),
                admission=PERMISSIVE_TEST_ADMISSION,
            )
            await runtime.initialize()
        before = [job.model_copy(deep=True) for job in await runtime.list_jobs()]
        with pytest.raises(TriggerError):
            await runtime._tick()
        assert await runtime.list_jobs() == before
        assert not runtime._background_tasks
    finally:
        await runtime.shutdown()


@pytest.mark.parametrize("now", [
    datetime(2000, 1, 1, tzinfo=UTC).replace(tzinfo=None),
    datetime.max.replace(tzinfo=UTC),
    datetime.max.replace(tzinfo=timezone(-timedelta(hours=1))),
    datetime.min.replace(tzinfo=timezone(timedelta(hours=1))),
])
def test_cron_without_representable_future_match_returns_none(now):
    trigger = Trigger(trigger_type=TriggerType.CRON, cron_expression="* * * * *")
    assert TriggerEngine.compute_next(trigger, now) is None

"""Renewal eligibility and expiry must use one Runtime Clock sample."""

from datetime import UTC, datetime, timedelta

import pytest

from core.scheduler.config import SchedulerConfig
from core.scheduler.models import ScheduleRequest, Trigger, TriggerType
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.runtime import SchedulerRuntime
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from tests.helpers.clock import MutableClock


class ProbeComplete(Exception):
    """Stop a test-only renewal loop after observing exactly one iteration."""


async def claimed_runtime(tmp_path, year):
    instant = datetime(year, 1, 1, tzinfo=UTC)
    clock = MutableClock(instant)
    persistence = SchedulerPersistence(str(tmp_path / "scheduler.db"))
    runtime = SchedulerRuntime(
        persistence=persistence, clock=clock,
        config=SchedulerConfig(persistence_enabled=True, claim_ttl_seconds=60),
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    await runtime.initialize()
    job = await runtime.schedule(ScheduleRequest(
        job_name="clock-renewal", workflow_name="unused",
        trigger=Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=instant),
    ))
    claimed = await persistence.claim_job(
        job.info.id, now=instant, claim_token="current-owner", run_id="probe-run",
        claim_expires_at=instant + timedelta(seconds=60),
    )
    assert claimed is not None
    return runtime, persistence, job.info.id, clock


def one_iteration_sleep(monkeypatch):
    calls = []

    async def sleep(delay):
        calls.append(delay)
        if len(calls) > 1:
            raise ProbeComplete

    monkeypatch.setattr("core.scheduler.runtime.asyncio.sleep", sleep)
    return calls


@pytest.mark.asyncio
@pytest.mark.parametrize("year", [2000, 2100])
async def test_live_lease_renews_using_runtime_time(tmp_path, monkeypatch, year):
    runtime, persistence, job_id, clock = await claimed_runtime(tmp_path, year)
    try:
        clock.advance(timedelta(seconds=10))
        one_iteration_sleep(monkeypatch)
        with pytest.raises(ProbeComplete):
            await runtime._renew_claim_loop(job_id, "current-owner")
        stored = await persistence.get_job(job_id)
        assert stored.updated_at == clock.now()
        assert stored.claim_expires_at == clock.now() + timedelta(seconds=60)
        assert stored.claim_token == "current-owner"
        assert stored.run_count == 0
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["expired", "wrong_owner"])
async def test_renewal_does_not_resurrect_or_take_over_lease(tmp_path, monkeypatch, reason):
    runtime, persistence, job_id, clock = await claimed_runtime(tmp_path, 2100)
    try:
        clock.advance(timedelta(seconds=61 if reason == "expired" else 10))
        token = "current-owner" if reason == "expired" else "wrong-owner"
        before = await persistence.get_job(job_id)
        sleeps = one_iteration_sleep(monkeypatch)
        await runtime._renew_claim_loop(job_id, token)
        assert sleeps == [20]
        assert await persistence.get_job(job_id) == before
    finally:
        await runtime.shutdown()


@pytest.mark.asyncio
async def test_renewal_samples_clock_once(monkeypatch):
    class AdvancingClock:
        calls = 0

        def now(self):
            self.calls += 1
            return datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=self.calls)

    class ProbePersistence:
        async def renew_claim(self, job_id, token, expires, *, now=None):
            assert now is not None
            assert expires == now + timedelta(seconds=60)
            return False

    clock = AdvancingClock()
    runtime = SchedulerRuntime(
        clock=clock, persistence=ProbePersistence(),
        config=SchedulerConfig(claim_ttl_seconds=60),
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    one_iteration_sleep(monkeypatch)
    await runtime._renew_claim_loop("probe", "current-owner")
    assert clock.calls == 1

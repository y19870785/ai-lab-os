"""Bounded real-time loop evidence, not production or cross-process acceptance."""

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

from core.errors import RuntimeStatus
from core.scheduler.config import SchedulerConfig
from core.scheduler.exceptions import JobClaimLostError
from core.scheduler.handlers import ActionHandlerRegistry
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import (
    JobRunStatus,
    JobStatus,
    ScheduleRequest,
    Trigger,
    TriggerType,
)
from core.scheduler.runtime import SchedulerRuntime
from core.system.admission import WorkAdmissionGate
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState
from tests.helpers.scheduler_timeline import SchedulerTimeline, TimelinePersistence


class ExecutionLedger:
    def __init__(self, timeline):
        self.timeline = timeline
        self.connections = 0
        self.active = set()
        self.started = []
        self.finished = []
        self.overlaps = []

    async def execute(self, job, run):
        if job.info.id in self.active:
            self.overlaps.append(job.info.id)
        self.active.add(job.info.id)
        identity = (job.info.id, run.id, run.attempt)
        self.started.append(identity)
        self.timeline.record("handler.start", job_id=job.info.id,
                             run_id=run.id, attempt=run.attempt)
        try:
            # Longer than the 0.6s lease: the competing loop observes renewals.
            await asyncio.sleep(1.2)
            self.finished.append(identity)
            self.timeline.record("handler.finish", job_id=job.info.id, run_id=run.id)
            return {"synthetic": True}
        finally:
            self.timeline.record("handler.exit", job_id=job.info.id, run_id=run.id)
            self.active.discard(job.info.id)


async def make_runtime(path, ledger):
    lifecycle = LifecycleStateMachine()
    await lifecycle.transition(SystemLifecycleState.STARTING)
    await lifecycle.transition(SystemLifecycleState.READY)
    handlers = ActionHandlerRegistry()
    handlers.register("isolated_probe", ledger)
    instance = ledger.connections
    ledger.connections += 1
    runtime = SchedulerRuntime(
        executor=JobExecutor(handler_registry=handlers),
        persistence=TimelinePersistence(path, ledger.timeline, instance),
        config=SchedulerConfig(
            persistence_enabled=True, tick_interval=0.04,
            claim_ttl_seconds=0.6, cancel_running_jobs_on_shutdown=False,
        ),
        admission=WorkAdmissionGate(lifecycle),
    )
    await runtime.initialize()
    return runtime


@pytest.fixture
def timeline(tmp_path):
    value = SchedulerTimeline()
    yield value
    artifact = tmp_path / "scheduler-timeline.json"
    value.save(artifact)
    print(f"Scheduler timeline: {artifact}; dropped={value.dropped}")


@pytest.mark.asyncio
async def test_sixty_second_competing_loops_survive_instance_restart(tmp_path, timeline):
    path = tmp_path / "isolated-scheduler.db"
    ledger = ExecutionLedger(timeline)
    loop = asyncio.get_running_loop()
    epoch_counts = []
    one_shot_id = interval_id = None
    for epoch in range(2):
        timeline.record("epoch.start", epoch=epoch)
        runtimes = []
        try:
            for _ in range(2):
                runtimes.append(await make_runtime(path, ledger))
            owner = runtimes[0]
            if epoch == 0:
                interval = await owner.schedule(ScheduleRequest(
                    job_name="interval-probe", action_type="isolated_probe",
                    trigger=Trigger(trigger_type=TriggerType.INTERVAL, interval_seconds=1),
                ))
                one_shot = await owner.schedule(ScheduleRequest(
                    job_name="one-shot-probe", action_type="isolated_probe",
                    trigger=Trigger(trigger_type=TriggerType.ONE_SHOT,
                                    run_at=datetime.now(UTC) - timedelta(seconds=1)),
                ))
                interval_id, one_shot_id = interval.info.id, one_shot.info.id
            else:
                recovered = await owner.get_job(one_shot_id)
                assert recovered.status == JobStatus.COMPLETED
                assert recovered.run_count == 1
            before = sum(item[0] == interval_id for item in ledger.finished)
            for runtime in runtimes:
                await runtime.start()
            deadline = loop.time() + 30
            tick_updates = {runtime: (None, loop.time()) for runtime in runtimes}
            completions = before
            progress_at = loop.time()
            samples = 0
            while loop.time() < deadline:
                expected_sample = loop.time() + 0.1
                await asyncio.sleep(0.1)
                timeline.record("loop.sample", epoch=epoch,
                                lag=max(0, loop.time() - expected_sample))
                for runtime in runtimes:
                    health = await runtime.health()
                    assert health["status"] == RuntimeStatus.OK.value, health
                    assert health["last_error"] is None
                    last_value, updated_at = tick_updates[runtime]
                    if health["last_successful_tick_at"] != last_value:
                        updated_at = loop.time()
                        tick_updates[runtime] = (health["last_successful_tick_at"], updated_at)
                    assert loop.time() - updated_at < 5, "Scheduler tick stopped progressing"
                current = sum(item[0] == interval_id for item in ledger.finished)
                if current != completions:
                    completions, progress_at = current, loop.time()
                assert loop.time() - progress_at < 10, "Interval job stopped progressing"
                assert not ledger.overlaps
                samples += 1
            assert samples >= 10
            for runtime in runtimes:
                assert (await runtime.health())["last_successful_tick_at"] is not None
        finally:
            for runtime in runtimes:
                await runtime.shutdown()
                assert runtime._tick_task is None
                assert not runtime._background_tasks
            timeline.record("epoch.shutdown", epoch=epoch)
        count = sum(item[0] == interval_id for item in ledger.finished) - before
        assert count >= 2
        epoch_counts.append(count)

    assert all(count >= 2 for count in epoch_counts)
    assert not ledger.active and not ledger.overlaps
    assert len(ledger.started) == len(ledger.finished)
    assert set(ledger.started) == set(ledger.finished)
    reader = await make_runtime(path, ledger)
    try:
        for job_id in (interval_id, one_shot_id):
            runs = await reader.list_job_runs(job_id)
            job = await reader.get_job(job_id)
            observed = [entry for entry in ledger.finished if entry[0] == job_id]
            assert len(runs) == job.run_count == len(observed)
            assert {run.id for run in runs} == {entry[1] for entry in observed}
            assert [run.attempt for run in runs] == list(range(1, len(runs) + 1))
            assert all(run.status == JobRunStatus.SUCCESS for run in runs)
            assert job.claim_token is None and job.claim_expires_at is None
        assert (await reader.get_job(one_shot_id)).run_count == 1
        assert timeline.dropped == 0
        timeline.record("verification.complete")
    finally:
        await reader.shutdown()


def _inject_loop_stall():
    """Deliberate diagnostic fault, never used by the unmodified 60s baseline."""
    time.sleep(1)


@pytest.mark.asyncio
async def test_timeline_records_injected_stall_and_claim_loss(tmp_path, timeline):
    ledger = ExecutionLedger(timeline)
    path = tmp_path / "injected-stall.db"
    owner = await make_runtime(path, ledger)
    peer = await make_runtime(path, ledger)
    try:
        job = await owner.schedule(ScheduleRequest(
            job_name="injected-stall", action_type="isolated_probe",
            trigger=Trigger(trigger_type=TriggerType.ONE_SHOT,
                            run_at=datetime.now(UTC) - timedelta(seconds=1)),
        ))
        await owner.start()

        async def wait_for_handler():
            while not ledger.active:
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_handler(), timeout=5)
        tasks = list(owner._background_tasks)
        assert len(tasks) == 1
        timeline.record("injection.loop_stall.begin")
        _inject_loop_stall()
        timeline.record("injection.loop_stall.end")
        # Observe expiry before letting the suspended owner continue.
        await peer._tick()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        assert any(isinstance(result, JobClaimLostError) for result in results)
        stored = await peer.get_job(job.info.id)
        runs = await peer.list_job_runs(job.info.id)
        assert stored.status == JobStatus.RETRYING
        assert len(runs) == 1
        assert runs[0].failure.code == "scheduler.job.claim_expired"
        assert any(event["event"] == "release.end" and event["released"] > 0
                   for event in timeline.events)
        assert any(event["event"] == "finalize.error"
                   and event["error_type"] == "JobClaimLostError"
                   for event in timeline.events)
    finally:
        await owner.shutdown()
        await peer.shutdown()

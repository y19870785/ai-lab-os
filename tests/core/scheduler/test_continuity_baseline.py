"""Bounded real-time loop evidence, not production or cross-process acceptance."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from core.errors import RuntimeStatus
from core.scheduler.config import SchedulerConfig
from core.scheduler.handlers import ActionHandlerRegistry
from core.scheduler.jobs import JobExecutor
from core.scheduler.models import (
    JobRunStatus,
    JobStatus,
    ScheduleRequest,
    Trigger,
    TriggerType,
)
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.runtime import SchedulerRuntime
from core.system.admission import WorkAdmissionGate
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState


class ExecutionLedger:
    def __init__(self):
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
        try:
            # Longer than the 0.6s lease: the competing loop observes renewals.
            await asyncio.sleep(1.2)
            self.finished.append(identity)
            return {"synthetic": True}
        finally:
            self.active.discard(job.info.id)


async def make_runtime(path, ledger):
    lifecycle = LifecycleStateMachine()
    await lifecycle.transition(SystemLifecycleState.STARTING)
    await lifecycle.transition(SystemLifecycleState.READY)
    handlers = ActionHandlerRegistry()
    handlers.register("isolated_probe", ledger)
    runtime = SchedulerRuntime(
        executor=JobExecutor(handler_registry=handlers),
        persistence=SchedulerPersistence(str(path)),
        config=SchedulerConfig(
            persistence_enabled=True, tick_interval=0.04,
            claim_ttl_seconds=0.6, cancel_running_jobs_on_shutdown=False,
        ),
        admission=WorkAdmissionGate(lifecycle),
    )
    await runtime.initialize()
    return runtime


@pytest.mark.asyncio
async def test_sixty_second_competing_loops_survive_instance_restart(tmp_path):
    path = tmp_path / "isolated-scheduler.db"
    ledger = ExecutionLedger()
    loop = asyncio.get_running_loop()
    epoch_counts = []
    one_shot_id = interval_id = None
    for epoch in range(2):
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
                await asyncio.sleep(0.1)
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
    finally:
        await reader.shutdown()

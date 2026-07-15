import asyncio
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from core.errors import ErrorCategory, failure_from_exception
from core.scheduler.config import SchedulerConfig
from core.scheduler.exceptions import JobClaimLostError
from core.scheduler.models import (
    JobRun,
    JobRunStatus,
    JobStatus,
    ScheduleRequest,
    Trigger,
    TriggerType,
)
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.runtime import SchedulerRuntime


pytestmark = pytest.mark.asyncio(loop_scope="function")


class SuccessExecutor:
    def __init__(self):
        self.calls = 0

    async def execute(self, job, run):
        self.calls += 1
        job.run_count += 1
        job.last_run_at = datetime.now(timezone.utc)
        job.last_result = JobRunStatus.SUCCESS.value
        return run.model_copy(update={
            "status": JobRunStatus.SUCCESS,
            "finished_at": datetime.now(timezone.utc),
        })


class MultiJobBlockingExecutor:
    def __init__(self):
        self.started = 0
        self.both_started = asyncio.Event()
        self.release = asyncio.Event()

    async def execute(self, job, run):
        self.started += 1
        if self.started == 2:
            self.both_started.set()
        await self.release.wait()
        job.run_count += 1
        return run.model_copy(update={
            "status": JobRunStatus.SUCCESS,
            "finished_at": datetime.now(timezone.utc),
        })


def _config(path):
    return SchedulerConfig(
        db_path=str(path),
        persistence_enabled=True,
        claim_ttl_seconds=0.1,
        retry_delay_seconds=0.01,
    )


async def _runtime(path, executor):
    persistence = SchedulerPersistence(str(path))
    runtime = SchedulerRuntime(
        registry=SchedulerRegistry(),
        executor=executor,
        persistence=persistence,
        config=_config(path),
    )
    await runtime.initialize()
    return runtime


async def _settle(runtime):
    tasks = list(runtime._background_tasks)
    if tasks:
        await asyncio.gather(*tasks)
    await asyncio.sleep(0)


async def test_one_shot_completes_and_never_fires_on_later_tick(tmp_path):
    executor = SuccessExecutor()
    runtime = await _runtime(tmp_path / "scheduler.db", executor)
    job = await runtime.schedule(ScheduleRequest(
        job_name="one-shot-terminal",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))

    await runtime._tick()
    await _settle(runtime)
    await runtime._tick()
    await _settle(runtime)

    persisted = await runtime.get_job(job.info.id)
    assert executor.calls == 1
    assert persisted.status == JobStatus.COMPLETED
    assert persisted.trigger.next_run_at is None
    assert persisted.claim_token is None
    assert persisted.claim_expires_at is None
    await runtime.shutdown()


async def test_two_runtime_connections_compete_with_database_cas(tmp_path):
    path = tmp_path / "scheduler.db"
    first = SuccessExecutor()
    runtime_a = await _runtime(path, first)
    job = await runtime_a.schedule(ScheduleRequest(
        job_name="cross-runtime",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    second = SuccessExecutor()
    runtime_b = await _runtime(path, second)

    await asyncio.gather(runtime_a._tick(), runtime_b._tick())
    await asyncio.gather(_settle(runtime_a), _settle(runtime_b))

    assert first.calls + second.calls == 1
    assert (await runtime_a._persistence.get_job(job.info.id)).status == JobStatus.COMPLETED
    await runtime_a.shutdown()
    await runtime_b.shutdown()


async def test_completed_one_shot_does_not_run_after_restart(tmp_path):
    path = tmp_path / "scheduler.db"
    first = SuccessExecutor()
    runtime_a = await _runtime(path, first)
    job = await runtime_a.schedule(ScheduleRequest(
        job_name="restart-terminal",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    await runtime_a._tick()
    await _settle(runtime_a)
    await runtime_a.shutdown()

    second = SuccessExecutor()
    runtime_b = await _runtime(path, second)
    await runtime_b._tick()
    await _settle(runtime_b)

    assert second.calls == 0
    assert (await runtime_b.get_job(job.info.id)).status == JobStatus.COMPLETED
    await runtime_b.shutdown()


async def test_old_claim_cannot_overwrite_new_owner(tmp_path):
    persistence = SchedulerPersistence(str(tmp_path / "scheduler.db"))
    await persistence.initialize()
    runtime = SchedulerRuntime(
        persistence=persistence,
        config=_config(tmp_path / "scheduler.db"),
    )
    await runtime.initialize()
    job = await runtime.schedule(ScheduleRequest(
        job_name="claim-owner",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    now = datetime.now(timezone.utc)
    first = await persistence.claim_job(
        job.info.id,
        now=now,
        claim_token="old-owner",
        claim_expires_at=now + timedelta(milliseconds=10),
        run_id="old-run",
    )
    await asyncio.sleep(0.02)
    await persistence.release_expired_claims(datetime.now(timezone.utc))
    second = await persistence.claim_job(
        job.info.id,
        now=datetime.now(timezone.utc),
        claim_token="new-owner",
        claim_expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        run_id="new-run",
    )
    run = JobRun(
        id="old-run", job_id=job.info.id, status=JobRunStatus.SUCCESS,
        claim_token="old-owner", finished_at=datetime.now(timezone.utc),
    )
    first.status = JobStatus.COMPLETED
    first.trigger.next_run_at = None

    with pytest.raises(JobClaimLostError):
        await persistence.finalize_claim(first, run, "old-owner")
    assert second.claim_token == "new-owner"
    await runtime.shutdown()


async def test_job_run_and_sanitized_failure_survive_restart(tmp_path):
    path = tmp_path / "scheduler.db"
    persistence = SchedulerPersistence(str(path))
    await persistence.initialize()
    runtime = SchedulerRuntime(persistence=persistence, config=_config(path))
    await runtime.initialize()
    job = await runtime.schedule(ScheduleRequest(
        job_name="failure-history",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    now = datetime.now(timezone.utc)
    claimed = await persistence.claim_job(
        job.info.id, now=now, claim_token="failure-owner",
        claim_expires_at=now + timedelta(seconds=1), run_id="failure-run",
    )
    failure = failure_from_exception(
        RuntimeError("secret database path C:/private/tasks.db"),
        component="scheduler.job", operation="execute",
        code="scheduler.job.execution_failed",
        category=ErrorCategory.EXECUTION_FAILURE,
        details={"job_id": job.info.id, "secret": "must-not-persist"},
    )
    run = JobRun(
        id="failure-run", job_id=job.info.id, status=JobRunStatus.FAILED,
        finished_at=datetime.now(timezone.utc), claim_token="failure-owner",
        failure=failure, trace_id="trace-safe",
    )
    claimed.status = JobStatus.FAILED
    claimed.last_error = failure
    claimed.run_count = 1
    claimed.last_result = JobRunStatus.FAILED.value
    claimed.last_run_at = run.finished_at
    claimed.trigger.next_run_at = None
    await persistence.finalize_claim(claimed, run, "failure-owner")
    await runtime.shutdown()

    reopened = SchedulerPersistence(str(path))
    await reopened.initialize()
    persisted_job = await reopened.get_job(job.info.id)
    runs = await reopened.list_job_runs(job.info.id)
    assert persisted_job.last_error.code == "scheduler.job.execution_failed"
    assert len(runs) == 1
    assert runs[0].failure.code == "scheduler.job.execution_failed"
    serialized = path.read_bytes()
    assert b"must-not-persist" not in serialized
    assert b"C:/private" not in serialized
    await reopened.close()


async def test_schema_migration_loads_legacy_workflow_job_idempotently(tmp_path):
    path = tmp_path / "legacy-scheduler.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT, version TEXT,
            tags TEXT, metadata TEXT, trigger_type TEXT, cron_expression TEXT,
            interval_seconds INTEGER, run_at TEXT, event_type TEXT,
            trigger_timezone TEXT, next_run_at TEXT, workflow_name TEXT,
            workflow_variables TEXT, status TEXT, max_retries INTEGER,
            timeout INTEGER, max_concurrent INTEGER, retry_count INTEGER,
            run_count INTEGER, last_run_at TEXT, last_result TEXT, created_at TEXT
        )
        """
    )
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "legacy-job", "legacy", "", "1.0.0", "[]", "{}", "one_shot", "",
            0, now, "", "UTC", now, "legacy-workflow", "{}", "active", 3,
            30, 1, 0, 0, None, "", now,
        ),
    )
    conn.commit()
    conn.close()

    persistence = SchedulerPersistence(str(path))
    await persistence.initialize()
    await persistence.close()
    await persistence.initialize()
    jobs = await persistence.load_jobs()
    assert len(jobs) == 1
    assert jobs[0].action_type == "workflow"
    assert jobs[0].claim_token is None
    assert jobs[0].revision == 1
    await persistence.close()


async def test_claim_renewal_requires_current_token(tmp_path):
    path = tmp_path / "scheduler.db"
    runtime = await _runtime(path, SuccessExecutor())
    job = await runtime.schedule(ScheduleRequest(
        job_name="renew-owner",
        workflow_name="workflow",
        trigger=Trigger(
            trigger_type=TriggerType.ONE_SHOT,
            run_at=datetime.now(timezone.utc) - timedelta(seconds=1),
        ),
    ))
    now = datetime.now(timezone.utc)
    await runtime._persistence.claim_job(
        job.info.id, now=now, claim_token="current-owner",
        claim_expires_at=now + timedelta(seconds=1), run_id="renew-run",
    )
    assert await runtime._persistence.renew_claim(
        job.info.id, "stale-owner", now + timedelta(seconds=2)
    ) is False
    assert await runtime._persistence.renew_claim(
        job.info.id, "current-owner", now + timedelta(seconds=2)
    ) is True
    await runtime.shutdown()


async def test_different_jobs_execute_concurrently_without_global_serial_lock(tmp_path):
    path = tmp_path / "scheduler.db"
    executor = MultiJobBlockingExecutor()
    persistence = SchedulerPersistence(str(path))
    runtime = SchedulerRuntime(
        executor=executor,
        persistence=persistence,
        config=SchedulerConfig(
            db_path=str(path), persistence_enabled=True,
            max_concurrent_jobs=2, claim_ttl_seconds=1,
        ),
    )
    await runtime.initialize()
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    for index in range(2):
        await runtime.schedule(ScheduleRequest(
            job_name=f"parallel-{index}",
            workflow_name="workflow",
            trigger=Trigger(trigger_type=TriggerType.ONE_SHOT, run_at=past),
        ))

    await runtime._tick()
    await asyncio.wait_for(executor.both_started.wait(), timeout=1)
    assert executor.started == 2
    executor.release.set()
    await _settle(runtime)
    assert all(job.status == JobStatus.COMPLETED for job in await runtime.list_jobs())
    await runtime.shutdown()

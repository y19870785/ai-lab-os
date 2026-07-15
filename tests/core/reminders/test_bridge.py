import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.database import DatabaseManager
from core.reminders import (
    ReminderActionHandler,
    ReminderSchedulerBridge,
    ReminderService,
    ReminderStatus,
    SQLiteReminderRepository,
    UserTaskReminderLifecycleCoordinator,
)
from core.reminders.exceptions import ReminderUnavailableError
from core.reminders.exceptions import ReminderPersistenceError
from core.errors import FailureException
from core.scheduler.exceptions import SchedulerPersistenceError
from core.scheduler.config import SchedulerConfig
from core.scheduler.handlers import ActionHandlerRegistry
from core.scheduler.jobs import JobExecutor
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.runtime import SchedulerRuntime
from core.user_tasks import SQLiteUserTaskRepository, UserTaskService, UserTaskStatus


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _stack(tmp_path):
    manager = DatabaseManager(tmp_path)
    task_repository = SQLiteUserTaskRepository(manager, tmp_path / "tasks.db")
    tasks = UserTaskService(task_repository)
    await tasks.initialize()
    reminder_repository = SQLiteReminderRepository(manager, tmp_path / "reminders.db")
    reminders = ReminderService(reminder_repository, tasks)
    await reminders.initialize()
    handlers = ActionHandlerRegistry()
    handlers.register("reminder", ReminderActionHandler(reminder_repository))
    scheduler_persistence = SchedulerPersistence(str(tmp_path / "scheduler.db"))
    scheduler = SchedulerRuntime(
        registry=SchedulerRegistry(),
        executor=JobExecutor(handler_registry=handlers),
        persistence=scheduler_persistence,
        config=SchedulerConfig(
            db_path=str(tmp_path / "scheduler.db"),
            persistence_enabled=True,
            claim_ttl_seconds=0.1,
            retry_delay_seconds=0.01,
        ),
    )
    await scheduler.initialize()
    bridge = ReminderSchedulerBridge(reminders, reminder_repository, scheduler, tasks)
    await bridge.initialize()
    tasks.set_lifecycle_coordinator(UserTaskReminderLifecycleCoordinator(bridge))
    return manager, tasks, reminder_repository, reminders, scheduler, bridge


async def _settle(runtime):
    tasks = list(runtime._background_tasks)
    if tasks:
        await asyncio.gather(*tasks)
    await asyncio.sleep(0)


async def test_create_trigger_and_repeated_ticks_produce_one_occurrence(tmp_path):
    manager, tasks, repository, _, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Follow up")
    reminder = await bridge.create(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(milliseconds=10),
        timezone_name="Asia/Shanghai",
    )
    await asyncio.sleep(0.02)
    await scheduler._tick()
    await _settle(scheduler)
    await scheduler._tick()
    await _settle(scheduler)

    stored = await repository.get(reminder.id)
    occurrences = await repository.list_occurrences(reminder.id)
    job = await scheduler.get_job(stored.scheduler_job_id)
    assert stored.status == ReminderStatus.TRIGGERED
    assert len(occurrences) == 1
    assert job.status.value == "completed"
    await scheduler.shutdown()
    manager.close_all()


async def test_reconciliation_is_idempotent_when_pending_schedule_has_no_job(tmp_path):
    manager, tasks, repository, reminders, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Reconcile")
    pending = await reminders.create_pending(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
        timezone_name="UTC",
    )

    first = await bridge.reconcile()
    second = await bridge.reconcile()
    stored = await repository.get(pending.id)

    assert first.repaired == 1
    assert first.failed == 0
    assert second.failed == 0
    assert stored.status == ReminderStatus.SCHEDULED
    assert stored.scheduler_job_id
    assert len([j for j in await scheduler.list_jobs() if j.info.name == f"reminder:{pending.id}"]) == 1
    await scheduler.shutdown()
    manager.close_all()


async def test_repeated_complete_retries_failed_reminder_cancellation(tmp_path, monkeypatch):
    manager, tasks, repository, _, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Lifecycle")
    reminder = await bridge.create(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
        timezone_name="UTC",
    )
    original_cancel = bridge.cancel
    attempts = 0

    async def fail_once(reminder_id, trace_id=""):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ReminderUnavailableError("injected cancellation failure")
        return await original_cancel(reminder_id, trace_id)

    monkeypatch.setattr(bridge, "cancel", fail_once)
    with pytest.raises(FailureException):
        await tasks.complete(task.id)

    assert (await tasks.get(task.id)).status == UserTaskStatus.COMPLETED
    assert (await repository.get(reminder.id)).status == ReminderStatus.PENDING_CANCEL
    assert (await tasks.health())["status"] == "degraded"

    completed = await tasks.complete(task.id)
    assert completed.status == UserTaskStatus.COMPLETED
    assert attempts == 2
    assert (await repository.get(reminder.id)).status == ReminderStatus.CANCELLED
    assert (await tasks.health())["status"] == "healthy"
    await scheduler.shutdown()
    manager.close_all()


async def test_handler_success_then_job_save_failure_recovers_without_duplicate_occurrence(
    tmp_path, monkeypatch
):
    manager, tasks, repository, _, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Failure window")
    reminder = await bridge.create(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(milliseconds=10),
        timezone_name="UTC",
    )
    original_finalize = scheduler._persistence.finalize_claim
    attempts = 0

    async def fail_terminal_save_once(job, run, token):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise SchedulerPersistenceError("injected terminal save failure")
        return await original_finalize(job, run, token)

    monkeypatch.setattr(scheduler._persistence, "finalize_claim", fail_terminal_save_once)
    await asyncio.sleep(0.02)
    await scheduler._tick()
    with pytest.raises(SchedulerPersistenceError):
        await _settle(scheduler)
    assert len(await repository.list_occurrences(reminder.id)) == 1

    await asyncio.sleep(0.12)
    await scheduler._tick()
    await _settle(scheduler)

    assert attempts == 2
    assert len(await repository.list_occurrences(reminder.id)) == 1
    assert (await scheduler.get_job(reminder.scheduler_job_id)).status.value == "completed"
    runs = await scheduler.list_job_runs(reminder.scheduler_job_id)
    assert [run.attempt for run in runs] == [1, 2]
    assert [run.status.value for run in runs] == ["failed", "success"]
    await scheduler.shutdown()
    manager.close_all()


async def test_reminder_state_save_failure_leaves_recoverable_evidence(tmp_path, monkeypatch):
    manager, tasks, repository, _, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Saga evidence")
    original_update = repository.update
    attempts = 0

    async def fail_once(reminder, revision):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ReminderPersistenceError("injected Reminder update failure")
        return await original_update(reminder, revision)

    monkeypatch.setattr(repository, "update", fail_once)
    with pytest.raises(FailureException) as captured:
        await bridge.create(
            user_task_id=task.id,
            remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
            timezone_name="UTC",
        )

    reminder_id = captured.value.failure.details["reminder_id"]
    stored = await repository.get(reminder_id)
    job = await scheduler.get_job(stored.scheduler_job_id)
    assert stored.status == ReminderStatus.FAILED
    assert stored.last_failure is not None
    assert job.status.value == "cancelled"
    first_reconcile = await bridge.reconcile()
    second_reconcile = await bridge.reconcile()
    recovered = await repository.get(reminder_id)
    assert first_reconcile.repaired == 1
    assert first_reconcile.failed == 0
    assert second_reconcile.failed == 0
    assert recovered.status == ReminderStatus.SCHEDULED
    assert recovered.scheduler_job_id == job.info.id
    await scheduler.shutdown()
    manager.close_all()


async def test_retry_exhaustion_persists_failed_job_reminder_and_one_occurrence(
    tmp_path, monkeypatch
):
    manager, tasks, repository, _, scheduler, bridge = await _stack(tmp_path)
    task = await tasks.create(title="Retry exhaustion")
    reminder = await bridge.create(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(milliseconds=10),
        timezone_name="UTC",
    )

    async def always_fail(*args, **kwargs):
        raise ReminderPersistenceError("injected trigger failure")

    monkeypatch.setattr(repository, "trigger", always_fail)
    await asyncio.sleep(0.02)
    for _ in range(3):
        await scheduler._tick()
        await _settle(scheduler)
        await asyncio.sleep(0.02)

    stored = await repository.get(reminder.id)
    occurrences = await repository.list_occurrences(reminder.id)
    job = await scheduler.get_job(reminder.scheduler_job_id)
    runs = await scheduler.list_job_runs(reminder.scheduler_job_id)
    assert stored.status == ReminderStatus.FAILED
    assert stored.last_failure is not None
    assert job.status.value == "failed"
    assert len(occurrences) == 1
    assert occurrences[0].status.value == "failed"
    assert occurrences[0].attempt == 3
    assert [run.status.value for run in runs] == ["failed", "failed", "failed"]
    reconciled = await bridge.reconcile()
    assert reconciled.failed == 0
    assert (await scheduler.get_job(reminder.scheduler_job_id)).status.value == "failed"
    assert (await repository.get(reminder.id)).status == ReminderStatus.FAILED
    await scheduler.shutdown()
    manager.close_all()

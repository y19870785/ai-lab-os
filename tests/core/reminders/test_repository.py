from datetime import datetime, timedelta, timezone
import asyncio

import pytest
from pydantic import ValidationError

from core.database import DatabaseManager
from core.reminders import Reminder, ReminderOccurrenceStatus, ReminderStatus
from core.reminders.exceptions import ReminderConflictError
from core.reminders.handler import ReminderActionHandler
from core.reminders.repository import SQLiteReminderRepository
from core.scheduler.models import Job, JobInfo, JobRun


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _repository(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteReminderRepository(manager, tmp_path / "reminders.db")
    await repository.initialize()
    return manager, repository


async def test_naive_datetime_and_invalid_timezone_are_rejected():
    with pytest.raises(ValidationError):
        Reminder(
            user_task_id="task-1",
            remind_at=datetime.now(),
            timezone="UTC",
        )
    with pytest.raises(ValidationError):
        Reminder(
            user_task_id="task-1",
            remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
            timezone="Mars/Olympus",
        )


async def test_trigger_is_effectively_once_at_database_boundary(tmp_path):
    manager, repository = await _repository(tmp_path)
    reminder = Reminder(
        user_task_id="task-1",
        remind_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        timezone="Asia/Shanghai",
        status=ReminderStatus.SCHEDULED,
    )
    await repository.create(reminder)

    first_reminder, first, first_idempotent = await repository.trigger(
        reminder.id, reminder.remind_at, "trace-1"
    )
    second_reminder, second, second_idempotent = await repository.trigger(
        reminder.id, reminder.remind_at, "trace-2"
    )

    assert first_reminder.status == ReminderStatus.TRIGGERED
    assert second_reminder.status == ReminderStatus.TRIGGERED
    assert first.id == second.id
    assert first.status == ReminderOccurrenceStatus.TRIGGERED
    assert first_idempotent is False
    assert second_idempotent is True
    assert len(await repository.list_occurrences(reminder.id)) == 1
    manager.close_all()


async def test_event_failure_does_not_roll_back_trigger(tmp_path):
    class BrokenBus:
        async def publish(self, *args, **kwargs):
            raise RuntimeError("event unavailable")

    manager, repository = await _repository(tmp_path)
    reminder = Reminder(
        user_task_id="task-1",
        remind_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        timezone="UTC",
        status=ReminderStatus.SCHEDULED,
    )
    await repository.create(reminder)
    handler = ReminderActionHandler(repository, BrokenBus())
    job = Job(
        info=JobInfo(name="reminder"),
        action_type="reminder",
        action_payload={
            "reminder_id": reminder.id,
            "scheduled_at": reminder.remind_at.isoformat(),
        },
    )

    result = await handler.execute(job, JobRun(job_id=job.info.id, trace_id="trace"))

    assert result["status"] == ReminderStatus.TRIGGERED.value
    assert (await repository.get(reminder.id)).status == ReminderStatus.TRIGGERED
    assert (await repository.health_check())["status"] == "degraded"
    manager.close_all()


async def test_repository_restart_preserves_reminder_and_occurrence(tmp_path):
    path = tmp_path / "reminders.db"
    first_manager = DatabaseManager(tmp_path)
    first_repository = SQLiteReminderRepository(first_manager, path)
    await first_repository.initialize()
    reminder = Reminder(
        user_task_id="task-1",
        remind_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        timezone="UTC",
        status=ReminderStatus.SCHEDULED,
    )
    await first_repository.create(reminder)
    await first_repository.trigger(reminder.id, reminder.remind_at, "trace")
    first_manager.close_all()

    second_manager = DatabaseManager(tmp_path)
    second_repository = SQLiteReminderRepository(second_manager, path)
    await second_repository.initialize()
    assert (await second_repository.get(reminder.id)).status == ReminderStatus.TRIGGERED
    assert len(await second_repository.list_occurrences(reminder.id)) == 1
    second_manager.close_all()


async def test_cancel_state_and_trigger_race_remains_consistent_across_connections(tmp_path):
    path = tmp_path / "reminders.db"
    manager_a = DatabaseManager(tmp_path / "a")
    manager_b = DatabaseManager(tmp_path / "b")
    repository_a = SQLiteReminderRepository(manager_a, path)
    repository_b = SQLiteReminderRepository(manager_b, path)
    await repository_a.initialize()
    await repository_b.initialize()
    reminder = Reminder(
        user_task_id="task-race",
        remind_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        timezone="UTC",
        status=ReminderStatus.SCHEDULED,
    )
    await repository_a.create(reminder)
    stale = await repository_b.get(reminder.id)

    async def trigger():
        try:
            await repository_a.trigger(reminder.id, reminder.remind_at, "trigger")
            return "triggered"
        except ReminderConflictError:
            return "conflict"

    async def cancel_state():
        try:
            await repository_b.update(
                stale.model_copy(update={"status": ReminderStatus.PENDING_CANCEL}),
                stale.revision,
            )
            return "pending_cancel"
        except ReminderConflictError:
            return "conflict"

    outcomes = await asyncio.gather(
        asyncio.to_thread(lambda: asyncio.run(trigger())),
        asyncio.to_thread(lambda: asyncio.run(cancel_state())),
    )
    stored = await repository_a.get(reminder.id)
    occurrences = await repository_a.list_occurrences(reminder.id)
    assert outcomes.count("conflict") == 1
    if stored.status == ReminderStatus.TRIGGERED:
        assert len(occurrences) == 1
    else:
        assert stored.status == ReminderStatus.PENDING_CANCEL
        assert occurrences == []
    manager_a.close_all()
    manager_b.close_all()

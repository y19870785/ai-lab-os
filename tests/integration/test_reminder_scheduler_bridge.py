import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.reminders import ReminderStatus
from core.system import create_system, make_test_settings


pytestmark = pytest.mark.asyncio(loop_scope="function")


def _settings(tmp_path):
    return make_test_settings(
        tmp_path, enable_scheduler=True, enable_reminders=True
    )


async def test_reminder_survives_restart_triggers_once_and_stays_terminal(tmp_path):
    settings = _settings(tmp_path)
    system_a = await create_system(settings)
    await system_a.start()
    task = await system_a.user_task_service.create(title="Restart reminder")
    reminder = await system_a.reminder_bridge.create(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(milliseconds=100),
        timezone_name="UTC",
    )
    await system_a.shutdown()

    system_b = await create_system(settings)
    await system_b.start()
    await asyncio.sleep(1.2)
    stored = await system_b.reminder_service.get(reminder.id)
    occurrences = await system_b.reminder_service.list_occurrences(reminder.id)
    job = await system_b.scheduler_runtime.get_job(stored.scheduler_job_id)
    assert stored.status == ReminderStatus.TRIGGERED
    assert len(occurrences) == 1
    assert job.status.value == "completed"
    await system_b.shutdown()

    system_c = await create_system(settings)
    await system_c.start()
    await asyncio.sleep(1.1)
    assert len(await system_c.reminder_service.list_occurrences(reminder.id)) == 1
    assert (await system_c.scheduler_runtime.get_job(stored.scheduler_job_id)).status.value == "completed"
    await system_c.shutdown()


async def test_startup_reconciliation_repairs_pending_schedule_once(tmp_path):
    settings = _settings(tmp_path)
    system_a = await create_system(settings)
    await system_a.start()
    task = await system_a.user_task_service.create(title="Pending reminder")
    pending = await system_a.reminder_service.create_pending(
        user_task_id=task.id,
        remind_at=datetime.now(timezone.utc) + timedelta(hours=1),
        timezone_name="UTC",
    )
    await system_a.shutdown()

    system_b = await create_system(settings)
    await system_b.start()
    repaired = await system_b.reminder_service.get(pending.id)
    second = await system_b.reminder_bridge.reconcile()
    assert repaired.status == ReminderStatus.SCHEDULED
    assert repaired.scheduler_job_id
    assert second.failed == 0
    assert len([
        job for job in await system_b.scheduler_runtime.list_jobs()
        if job.info.name == f"reminder:{pending.id}"
    ]) == 1
    await system_b.shutdown()


async def test_enabled_reminders_without_scheduler_make_system_health_failed(tmp_path):
    settings = make_test_settings(
        tmp_path, enable_scheduler=False, enable_reminders=True
    )
    system = await create_system(settings)
    await system.start()
    health = await system.health()
    assert health["status"] == "failed"
    assert health["components"]["reminders"]["status"] == "failed"
    assert health["components"]["reminders"]["bridge"]["reason"] == "scheduler_not_configured"
    await system.shutdown()

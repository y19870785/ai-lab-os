from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from cli.commands import reminder_status_cmd
from core.system import create_system, load_system_settings


def _configure(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "mock")
    monkeypatch.setenv("AI_LAB_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("AI_LAB_SQLITE_DIR", str(tmp_path / "sqlite"))
    monkeypatch.setenv("AI_LAB_ENABLE_USER_TASKS", "true")
    monkeypatch.setenv("AI_LAB_ENABLE_REMINDERS", "true")
    monkeypatch.setenv("AI_LAB_ENABLE_SCHEDULER", "true")
    monkeypatch.setenv("AI_LAB_TIMEZONE", "Asia/Shanghai")


async def _create_persisted_reminder():
    system = await create_system(load_system_settings(load_dotenv=False))
    await system.start()
    try:
        task = await system.user_task_service.create(
            title="CLI status acceptance",
            due_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            timezone="Asia/Shanghai",
        )
        reminder = await system.reminder_bridge.create(
            user_task_id=task.id,
            remind_at=task.due_at,
            timezone_name=task.timezone,
        )
        return reminder.id
    finally:
        await system.shutdown()


def test_reminder_status_command_uses_real_composition_root(
    monkeypatch, tmp_path, capsys
):
    _configure(monkeypatch, tmp_path)
    reminder_id = asyncio.run(_create_persisted_reminder())

    asyncio.run(reminder_status_cmd.run([reminder_id]))

    output = json.loads(capsys.readouterr().out)
    assert output["reminder_id"] == reminder_id
    assert output["status"] == "scheduled"
    assert output["scheduler_job_id"]

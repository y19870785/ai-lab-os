from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone

from cli.commands import reminders_cmd
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
            title="联系张经理",
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


def test_reminders_cli_reads_real_persisted_inbox_in_human_and_json_modes(
    monkeypatch, tmp_path, capsys
):
    _configure(monkeypatch, tmp_path)
    reminder_id = asyncio.run(_create_persisted_reminder())

    asyncio.run(reminders_cmd.run(["--status", "scheduled"]))
    human = capsys.readouterr().out
    assert "联系张经理" in human
    assert reminder_id in human
    assert "scheduled" in human

    asyncio.run(reminders_cmd.run(["--status", "scheduled", "--json"]))
    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 1
    assert payload["items"][0]["reminder_id"] == reminder_id
    assert payload["items"][0]["task_title"] == "联系张经理"

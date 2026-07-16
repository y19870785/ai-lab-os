from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

from core.system import create_system, load_system_settings


def _env(tmp_path) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_DATA_DIR": str(tmp_path),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
        "AI_LAB_ENABLE_USER_TASKS": "true",
        "AI_LAB_ENABLE_REMINDERS": "true",
        "AI_LAB_ENABLE_SCHEDULER": "true",
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_API_AUTH_ENABLED": "false",
        "AI_LAB_SCHEDULER_TICK_INTERVAL": "60",
    })
    env.pop("PYTHONIOENCODING", None)
    return env


async def _seed(env):
    previous = os.environ.copy()
    os.environ.update(env)
    try:
        system = await create_system(load_system_settings(load_dotenv=False))
        await system.start()
        try:
            due = datetime.now(timezone.utc) + timedelta(days=1)
            reminders = []
            for title in ("联系张经理确认蜂蜡检测方案", "整理中文报价"):
                task = await system.user_task_service.create(
                    title=title, due_at=due, timezone="Asia/Shanghai"
                )
                reminders.append(await system.reminder_bridge.create(
                    user_task_id=task.id,
                    remind_at=due,
                    timezone_name="Asia/Shanghai",
                ))
            return reminders
        finally:
            await system.shutdown()
    finally:
        os.environ.clear()
        os.environ.update(previous)


def _run(env, *args):
    return subprocess.run(
        [sys.executable, "-m", "cli", *args],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        check=False,
        timeout=30,
    )


def test_cli_management_commands_emit_clean_utf8_and_json(tmp_path):
    env = _env(tmp_path)
    first, second = asyncio.run(_seed(env))

    pending = _run(env, "reminders", "--pending", "--json")
    assert pending.returncode == 0
    assert pending.stderr == b""
    pending_json = json.loads(pending.stdout.decode("utf-8"))
    assert {item["task_title"] for item in pending_json["items"]} == {
        "联系张经理确认蜂蜡检测方案", "整理中文报价",
    }

    detail = _run(env, "reminder-status", first.id, "--human")
    assert detail.returncode == 0
    assert detail.stderr == b""
    assert "联系张经理确认蜂蜡检测方案" in detail.stdout.decode("utf-8")

    cancelled = _run(env, "reminder-cancel", first.id, "--json")
    assert cancelled.returncode == 0
    assert cancelled.stderr == b""
    assert json.loads(cancelled.stdout.decode("utf-8"))["current"]["status"] == "cancelled"

    target = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    changed = _run(
        env,
        "reminder-reschedule", second.id,
        "--scheduled-for", target,
        "--timezone", "Asia/Shanghai",
        "--idempotency-key", "cli-reschedule-key",
        "--json",
    )
    assert changed.returncode == 0
    assert changed.stderr == b""
    changed_json = json.loads(changed.stdout.decode("utf-8"))
    assert changed_json["current"]["status"] == "scheduled"
    assert changed_json["current"]["task_title"] == "整理中文报价"

    missing = _run(env, "reminder-cancel", "rem_missing")
    assert missing.returncode == 2
    assert missing.stdout == b""
    assert "reminder.not_found" in missing.stderr.decode("utf-8")

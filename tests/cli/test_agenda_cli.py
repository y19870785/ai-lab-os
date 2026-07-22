import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from core.errors import ErrorCategory, FailureInfo
from core.memory.models import MemoryQuery, MemoryType
from core.reminders.inbox import normalized_workspace
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey


def _run_agenda(args_str, tmp_path, extra_env=None):
    env = os.environ.copy()
    env["AI_LAB_DATA_DIR"] = str(tmp_path)
    env["AI_LAB_SQLITE_DIR"] = str(tmp_path / "sqlite")
    env["AI_LAB_PROVIDER_MODE"] = "mock"
    env["AI_LAB_ENABLE_REMINDERS"] = "true"
    env["AI_LAB_ENABLE_SCHEDULER"] = "true"
    env["AI_LAB_TIMEZONE"] = "Asia/Shanghai"
    env["AI_LAB_API_AUTH_ENABLED"] = "false"
    env["PYTHONIOENCODING"] = "utf-8"
    for k in ("AI_LAB_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY",
              "ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
        env.pop(k, None)
    if extra_env:
        env.update(extra_env)
    python_executable = sys.executable
    cmd = [python_executable, "-m", "cli", "agenda"] + args_str.split()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env,
                          encoding="utf-8", cwd=str(Path(__file__).parent.parent.parent))
    return proc


def test_agenda_cli_today_json_pure_stdout(tmp_path):
    (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)
    proc = _run_agenda("--today --json", tmp_path)
    assert proc.returncode == 0
    assert proc.stdout.strip()
    data = json.loads(proc.stdout)
    assert data["view"] == "today"
    assert data["timezone"] == "Asia/Shanghai"


def test_agenda_cli_next_3(tmp_path):
    (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)
    proc = _run_agenda("--next 3 --json", tmp_path)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["view"] == "next"


def test_agenda_cli_remains_available_when_reminders_are_disabled(tmp_path):
    proc = _run_agenda(
        "--today --json",
        tmp_path,
        extra_env={
            "AI_LAB_ENABLE_REMINDERS": "false",
            "AI_LAB_ENABLE_SCHEDULER": "false",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["view"] == "today"


def test_query_daily_agenda_uses_canonical_default_workspace(monkeypatch, tmp_path):
    from cli import runtime

    captured = {}

    class Agenda:
        async def list(self, **kwargs):
            captured.update(kwargs)
            return object()

    class System:
        daily_agenda = Agenda()

        async def start(self):
            pass

        async def shutdown(self):
            pass

    monkeypatch.setattr(
        runtime,
        "load_system_settings",
        lambda: make_test_settings(tmp_path, enable_scheduler=True, enable_reminders=True),
    )
    monkeypatch.setattr(runtime, "create_system", lambda settings: asyncio.sleep(0, result=System()))

    asyncio.run(runtime.query_daily_agenda(view="all"))

    assert isinstance(captured["workspace_key"], WorkspaceKey)
    assert normalized_workspace(captured["workspace_key"]) == {
        "tenant_id": "default",
        "workspace_id": "default",
        "namespace": "default",
    }


async def _snapshot(path):
    system = await create_system(
        make_test_settings(
            path,
            enable_scheduler=True,
            enable_reminders=True,
            timezone_name="Asia/Shanghai",
            scheduler_tick_interval=3600,
        )
    )
    await system.start()
    try:
        tasks = await system.user_task_service.list(limit=500)
        reminders = await system.reminder_service.list_page(limit=500, offset=0)
        memories = await system.memory_manager.retrieve_memory(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=1000)
        )
        work_logs = [m for m in memories if (m.content or {}).get("type") == "work_log"]
        return {
            "tasks": {t.id for t in tasks},
            "reminders": {r.id for r in reminders},
            "work_logs": {m.id for m in work_logs},
        }
    finally:
        await system.shutdown()


async def _seed_workspace_agenda(path):
    system = await create_system(
        make_test_settings(
            path,
            enable_scheduler=True,
            enable_reminders=True,
            timezone_name="Asia/Shanghai",
            scheduler_tick_interval=3600,
        )
    )
    await system.start()
    try:
        now = datetime.now(timezone.utc).replace(microsecond=0)
        business_timezone = ZoneInfo("Asia/Shanghai")
        business_date = now.astimezone(business_timezone).date()

        async def task(title, *, due_at=None, workspace="default"):
            return await system.user_task_service.create(
                title=title,
                due_at=due_at,
                timezone="Asia/Shanghai",
                source="test",
                metadata={
                    "workspace": {
                        "tenant_id": "default",
                        "workspace_id": workspace,
                        "namespace": "default",
                    }
                },
            )

        async def reminder(title, when, *, workspace="default"):
            created_task = await task(title, due_at=when, workspace=workspace)
            created_reminder = await system.reminder_bridge.create(
                user_task_id=created_task.id,
                remind_at=when,
                timezone_name="Asia/Shanghai",
            )
            return created_task, created_reminder

        overdue = await task("overdue", due_at=now - timedelta(hours=1))
        _, failed = await reminder("failed", now + timedelta(hours=4))
        await system.reminder_repository.record_trigger_failure(
            failed.id,
            failed.remind_at,
            "test",
            FailureInfo(
                code="test.reminder_failed",
                category=ErrorCategory.EXECUTION_FAILURE,
                message="Expected test failure",
                component="reminder.action",
                operation="trigger",
                retryable=False,
            ),
        )
        _, triggered = await reminder("triggered", now + timedelta(hours=5))
        triggered, occurrence, _ = await system.reminder_repository.trigger(
            triggered.id, triggered.remind_at, "test"
        )
        _, normal = await reminder("normal", now + timedelta(hours=2))
        _, next_five = await reminder("five-hours", now + timedelta(hours=5))
        _, foreign = await reminder("foreign", now + timedelta(hours=1), workspace="foreign")

        today_log = await system.memory_manager.save_memory(
            MemoryType.EPISODIC,
            {
                "type": "work_log",
                "date": business_date.isoformat(),
                "subject": "today log",
                "metadata": {"workspace_id": "default"},
            },
        )
        yesterday_log = await system.memory_manager.save_memory(
            MemoryType.EPISODIC,
            {
                "type": "work_log",
                "date": (business_date - timedelta(days=1)).isoformat(),
                "subject": "yesterday log",
                "metadata": {"workspace_id": "default"},
            },
        )
        foreign_log = await system.memory_manager.save_memory(
            MemoryType.EPISODIC,
            {
                "type": "work_log",
                "date": business_date.isoformat(),
                "subject": "foreign log",
                "metadata": {"workspace_id": "foreign"},
            },
        )
        return {
            "overdue": overdue.id,
            "failed": failed.id,
            "triggered": triggered.id,
            "normal": normal.id,
            "next_five": next_five.id,
            "foreign": foreign.id,
            "today_log": today_log,
            "yesterday_log": yesterday_log,
            "foreign_log": foreign_log,
            "occurrence": occurrence.id,
        }
    finally:
        await system.shutdown()


def test_agenda_cli_all_views_preserve_workspace_and_persisted_state(tmp_path):
    (tmp_path / "sqlite").mkdir(parents=True, exist_ok=True)
    seeded = asyncio.run(_seed_workspace_agenda(tmp_path))
    before = asyncio.run(_snapshot(tmp_path))

    pages = {}
    for command, expected_view in (
        ("--today --json", "today"),
        ("--next 3 --json", "next"),
        ("--attention --json", "attention"),
        ("--completed --json", "completed"),
        ("--all --json", "all"),
    ):
        proc = _run_agenda(command, tmp_path)
        assert proc.returncode == 0, proc.stderr
        pages[expected_view] = json.loads(proc.stdout)
        assert pages[expected_view]["view"] == expected_view

    attention_ids = {item["source_id"] for item in pages["attention"]["items"]}
    assert seeded["overdue"] in attention_ids
    assert seeded["failed"] in attention_ids
    assert seeded["normal"] not in attention_ids

    completed_ids = {item["source_id"] for item in pages["completed"]["items"]}
    assert seeded["triggered"] in completed_ids
    assert seeded["today_log"] in completed_ids
    assert seeded["yesterday_log"] not in completed_ids

    next_ids = {item["source_id"] for item in pages["next"]["items"]}
    assert seeded["normal"] in next_ids
    assert seeded["next_five"] not in next_ids

    for page in pages.values():
        page_ids = {item["source_id"] for item in page["items"]}
        assert seeded["foreign"] not in page_ids
        assert seeded["foreign_log"] not in page_ids

    after = asyncio.run(_snapshot(tmp_path))
    assert after == before

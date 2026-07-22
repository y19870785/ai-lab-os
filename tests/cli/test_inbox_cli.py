import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cli import runtime
from core.inbox.models import canonical_workspace
from core.system import make_test_settings
from core.workspace.models import WorkspaceKey


ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, *args):
    env = os.environ.copy()
    env.update({
        "AI_LAB_DATA_DIR": str(tmp_path),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_ENABLE_REMINDERS": "true",
        "AI_LAB_ENABLE_SCHEDULER": "true",
        "AI_LAB_TIMEZONE": "Asia/Shanghai",
        "AI_LAB_API_AUTH_ENABLED": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    for key in ("AI_LAB_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-m", "cli", "inbox", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def _add(tmp_path, content):
    result = _run(tmp_path, "add", content, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_inbox_cli_add_list_show_note_and_dismiss_json(tmp_path):
    first = _add(tmp_path, "先保存这个想法")
    second = _add(tmp_path, "无价值记录")

    listed = _run(tmp_path, "list", "--json")
    shown = _run(tmp_path, "show", first["id"], "--json")
    note = _run(tmp_path, "resolve-note", first["id"], "--json")
    dismissed = _run(tmp_path, "dismiss", second["id"], "--json")

    assert listed.returncode == shown.returncode == note.returncode == dismissed.returncode == 0
    assert {item["id"] for item in json.loads(listed.stdout)["items"]} == {
        first["id"], second["id"]
    }
    assert json.loads(shown.stdout)["source"] == "cli"
    assert json.loads(note.stdout)["resolved_type"] == "note"
    assert json.loads(dismissed.stdout)["status"] == "dismissed"
    assert json.loads(_run(tmp_path, "list", "--json").stdout)["items"] == []


def test_inbox_cli_resolve_task_reminder_and_work_log(tmp_path):
    task_item = _add(tmp_path, "跟进客户")
    reminder_item = _add(tmp_path, "联系供应商")
    work_log_item = _add(tmp_path, "完成验货")
    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

    task = _run(
        tmp_path,
        "resolve-task", task_item["id"], "--title", "跟进客户", "--json",
    )
    reminder = _run(
        tmp_path,
        "resolve-reminder", reminder_item["id"],
        "--title", "联系供应商", "--scheduled-at", scheduled_at, "--json",
    )
    work_log = _run(
        tmp_path,
        "resolve-work-log", work_log_item["id"], "--title", "完成验货", "--json",
    )

    assert task.returncode == reminder.returncode == work_log.returncode == 0
    assert json.loads(task.stdout)["resolved_type"] == "user_task"
    assert json.loads(reminder.stdout)["resolved_type"] == "reminder"
    assert json.loads(work_log.stdout)["resolved_type"] == "work_log"


def test_inbox_cli_nonzero_exit_on_failure(tmp_path):
    result = _run(tmp_path, "show", "inbox_missing", "--json")

    assert result.returncode == 2
    assert "inbox.not_found" in result.stderr
    assert result.stdout == ""


def test_inbox_cli_resolve_waiting_for_plain_json_and_validation(tmp_path):
    first = _add(tmp_path, "等张经理回复")
    review_at = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    plain = _run(
        tmp_path,
        "resolve-waiting-for",
        first["id"],
        "--subject",
        "蜂蜡检测方案",
        "--waiting-on",
        "张经理",
        "--next-review-at",
        review_at,
        "--timezone",
        "Asia/Shanghai",
    )
    repeated = _run(
        tmp_path,
        "resolve-waiting-for",
        first["id"],
        "--subject",
        "蜂蜡检测方案",
        "--waiting-on",
        "张经理",
        "--next-review-at",
        review_at,
        "--json",
    )
    missing = _run(
        tmp_path,
        "resolve-waiting-for",
        first["id"],
        "--subject",
        "蜂蜡检测方案",
        "--waiting-on",
        "张经理",
    )

    assert plain.returncode == repeated.returncode == 0
    assert "已创建等待事项：wf_inbox_" in plain.stdout
    payload = json.loads(repeated.stdout)
    assert payload["resolved_type"] == "waiting_for"
    assert payload["resolved_target_id"].startswith("wf_inbox_")
    assert missing.returncode == 2
    assert "--expected-by or --next-review-at is required" in missing.stderr


def test_inbox_runtime_uses_canonical_default_workspace(monkeypatch, tmp_path):
    captured = {}

    class Service:
        async def list(self, **kwargs):
            captured.update(kwargs)
            return object()

    class System:
        inbox_service = Service()

        async def start(self):
            return None

        async def shutdown(self):
            return None

    monkeypatch.setattr(runtime, "load_system_settings", lambda: make_test_settings(tmp_path))
    monkeypatch.setattr(
        runtime, "create_system", lambda _settings: asyncio.sleep(0, result=System())
    )

    asyncio.run(runtime.execute_inbox_operation("list", status="all"))

    assert isinstance(captured["workspace_key"], WorkspaceKey)
    assert canonical_workspace(captured["workspace_key"]).workspace_id == "default"

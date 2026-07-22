import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

from cli.commands import waiting_for_cmd
from core.waiting_for import WaitingFor, WaitingForMutationResult
from core.workspace.models import WorkspaceKey


ROOT = Path(__file__).resolve().parents[2]


def _run(tmp_path, *args):
    env = os.environ.copy()
    env.update({
        "AI_LAB_DATA_DIR": str(tmp_path),
        "AI_LAB_SQLITE_DIR": str(tmp_path / "sqlite"),
        "AI_LAB_PROVIDER_MODE": "mock",
        "AI_LAB_ENABLE_REMINDERS": "false",
        "AI_LAB_ENABLE_SCHEDULER": "false",
        "AI_LAB_API_AUTH_ENABLED": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    for key in ("AI_LAB_LLM_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-m", "cli", "waiting-for", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_waiting_for_cli_create_json_uses_thin_runtime(monkeypatch, capsys):
    captured = {}
    now = datetime(2026, 7, 22, 8, tzinfo=timezone.utc)
    item = WaitingFor(
        workspace_key=WorkspaceKey(),
        subject="供应商回复",
        waiting_on="供应商",
        source="cli",
        created_at=now,
        updated_at=now,
    )

    async def execute(operation, **values):
        captured.update(operation=operation, **values)
        return item

    monkeypatch.setattr(waiting_for_cmd, "execute_waiting_for_operation", execute)
    result = asyncio.run(waiting_for_cmd.run([
        "create", "--subject", "供应商回复", "--waiting-on", "供应商", "--json"
    ]))
    assert result == 0
    assert captured == {
        "operation": "create",
        "subject": "供应商回复",
        "waiting_on": "供应商",
        "context": "",
        "timezone": "UTC",
    }
    assert json.loads(capsys.readouterr().out)["id"] == item.id


def test_waiting_for_cli_resolve_maps_revision_and_note(monkeypatch, capsys):
    captured = {}
    now = datetime(2026, 7, 22, 8, tzinfo=timezone.utc)
    item = WaitingFor(
        workspace_key=WorkspaceKey(), subject="A", waiting_on="B", source="cli",
        created_at=now, updated_at=now,
    )

    async def execute(operation, **values):
        captured.update(operation=operation, **values)
        return WaitingForMutationResult(item=item, event={
            "waiting_for_id": item.id,
            "workspace_key": item.workspace_key,
            "sequence": 1,
            "event_type": "resolved",
            "occurred_at": now,
            "note": "完成",
            "source": "cli",
        })

    monkeypatch.setattr(waiting_for_cmd, "execute_waiting_for_operation", execute)
    assert asyncio.run(waiting_for_cmd.run([
        "resolve", item.id, "--expected-revision", "3", "--note", "完成", "--json"
    ])) == 0
    assert captured["expected_revision"] == 3
    assert captured["resolution_note"] == "完成"
    assert "event" in json.loads(capsys.readouterr().out)


def test_waiting_for_cli_real_entry_persists_and_lists(tmp_path):
    created = _run(
        tmp_path,
        "create",
        "--subject",
        "等待法务回复",
        "--waiting-on",
        "法务",
        "--json",
    )
    assert created.returncode == 0, created.stderr
    item_id = json.loads(created.stdout)["item"]["id"]
    listed = _run(tmp_path, "list", "--json")
    assert listed.returncode == 0, listed.stderr
    assert [item["id"] for item in json.loads(listed.stdout)["items"]] == [item_id]

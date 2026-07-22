import asyncio
import json
from datetime import datetime, timezone

from cli.commands import waiting_for_cmd
from core.waiting_for import WaitingFor, WaitingForMutationResult
from core.workspace.models import WorkspaceKey


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

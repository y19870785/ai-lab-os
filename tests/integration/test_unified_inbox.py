import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from core.errors import FailureException
from core.inbox import InboxStatus
from core.system import create_system
from core.system import make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


def _settings(path):
    return make_test_settings(
        path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=0.01,
    )


def _cli(path, *args):
    env = os.environ.copy()
    env.update({
        "AI_LAB_DATA_DIR": str(path),
        "AI_LAB_SQLITE_DIR": str(path / "sqlite"),
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


def test_assistant_capture_cli_list_api_task_resolution_reaches_agenda(tmp_path):
    with TestClient(create_app(_settings(tmp_path), clock=MutableClock(NOW))) as client:
        capture = client.post(
            "/chat", json={"user_input": "记一下，下周和包装供应商确认新版瓶盖"}
        )
        item_id = capture.json()["metadata"]["inbox_item"]["id"]

        listed = _cli(tmp_path, "list", "--json")
        assert listed.returncode == 0, listed.stderr
        assert item_id in {item["id"] for item in json.loads(listed.stdout)["items"]}

        resolved = client.post(
            f"/inbox/{item_id}/resolve/task",
            json={
                "title": "确认新版瓶盖",
                "due_at": (NOW + timedelta(hours=4)).isoformat(),
            },
        )
        assert resolved.status_code == 200
        target_id = resolved.json()["resolved_target_id"]
        agenda = client.get("/agenda?view=today").json()
        assert target_id in {item["task_id"] for item in agenda["items"]}


def test_api_capture_cli_reminder_resolution_is_visible_to_assistant(tmp_path):
    with TestClient(create_app(_settings(tmp_path), clock=MutableClock(NOW))) as client:
        item = client.post("/inbox", json={"content": "联系包装供应商"}).json()
        scheduled = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()

        resolved = _cli(
            tmp_path,
            "resolve-reminder",
            item["id"],
            "--title",
            "联系包装供应商",
            "--scheduled-at",
            scheduled,
            "--json",
        )
        assert resolved.returncode == 0, resolved.stderr
        reminder_id = json.loads(resolved.stdout)["resolved_target_id"]

        query = client.post("/chat", json={"user_input": "查看我的提醒"})
        assert query.status_code == 200
        body = query.json()
        assert body["metadata"]["intent"] == "reminder_list"
        assert reminder_id in query.text


def test_resolved_target_and_idempotency_survive_restart(tmp_path):
    import asyncio

    async def scenario():
        workspace = WorkspaceKey()
        first = await create_system(_settings(tmp_path), clock=MutableClock(NOW))
        await first.start()
        item = await first.inbox_service.capture(
            workspace_key=workspace, content="重启后不重复", source="api"
        )
        resolved = await first.inbox_service.resolve_to_task(
            workspace_key=workspace,
            inbox_item_id=item.id,
            title="重启后不重复",
        )
        target_id = resolved.resolved_target_id
        await first.shutdown()

        second = await create_system(_settings(tmp_path), clock=MutableClock(NOW))
        await second.start()
        try:
            restored = await second.inbox_service.get(
                workspace_key=workspace, inbox_item_id=item.id
            )
            before = {task.id for task in await second.user_task_service.list(limit=100)}
            try:
                await second.inbox_service.resolve_to_task(
                    workspace_key=workspace,
                    inbox_item_id=item.id,
                    title="重启后不重复",
                )
            except FailureException as exc:
                assert exc.failure.code == "inbox.already_resolved"
            else:
                raise AssertionError("repeat resolution must report a stable conflict")
            after = {task.id for task in await second.user_task_service.list(limit=100)}
            assert restored.status == InboxStatus.RESOLVED
            assert restored.resolved_target_id == target_id
            assert before == after == {target_id}
        finally:
            await second.shutdown()

    asyncio.run(scenario())

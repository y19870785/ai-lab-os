from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from applications.ceo_assistant.intent import IntentEffect, decide_intent
from core.memory.models import MemoryQuery, MemoryType
from core.system import make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


def _settings(path):
    return make_test_settings(
        path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=0.01,
    )


def _snapshot(system):
    import asyncio

    async def collect():
        inbox = await system.inbox_service.list(
            workspace_key=WorkspaceKey(),
            status="all",
            limit=200,
        )
        tasks = await system.user_task_service.list(limit=200)
        reminders = await system.reminder_service.list_page(limit=200, offset=0)
        memories = await system.memory_stores[1].query(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=200)
        )
        return {
            "inbox": {item.id for item in inbox.items},
            "tasks": {item.id for item in tasks},
            "reminders": {item.id for item in reminders},
            "work_logs": {item.id for item in memories if item.content.get("type") == "work_log"},
        }

    return asyncio.run(collect())


def test_inbox_capture_is_deterministic_and_creates_only_inbox_item(tmp_path):
    with TestClient(create_app(_settings(tmp_path), clock=MutableClock(NOW))) as client:
        before = _snapshot(client.app.state.system)
        response = client.post(
            "/chat", json={"user_input": "记一下，下周和包装供应商确认新版瓶盖"}
        )
        after = _snapshot(client.app.state.system)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["intent"] == "inbox_capture"
        assert body["metadata"]["effect"] == "write"
        assert body["metadata"]["inbox_item"]["source"] == "ceo_assistant"
        assert len(after["inbox"] - before["inbox"]) == 1
        assert after["tasks"] == before["tasks"]
        assert after["reminders"] == before["reminders"]
        assert after["work_logs"] == before["work_logs"]
        assert "MOCK MODE" not in body["answer"]
        assert "API_KEY" not in body["answer"]


def test_inbox_list_is_read_only_and_has_no_mock_noise(tmp_path):
    with TestClient(create_app(_settings(tmp_path), clock=MutableClock(NOW))) as client:
        client.post("/inbox", json={"content": "待整理记录"})
        before = _snapshot(client.app.state.system)
        response = client.post("/chat", json={"user_input": "看看我的收件箱"})
        after = _snapshot(client.app.state.system)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["intent"] == "inbox_list"
        assert body["metadata"]["effect"] == "read"
        assert before == after
        assert "待整理记录" in body["answer"]
        assert "MOCK MODE" not in body["answer"]


def test_existing_intents_do_not_drift_to_inbox():
    expected = {
        "提醒我明天下午三点开会": ("task", IntentEffect.WRITE),
        "记一下，下周和包装供应商确认新版瓶盖": (
            "inbox_capture", IntentEffect.WRITE,
        ),
        "看看我的收件箱": ("inbox_list", IntentEffect.READ),
        "记录一下今天完成了报价审核": ("work_log", IntentEffect.WRITE),
        "创建任务：整理客户需求": ("task", IntentEffect.WRITE),
        "今天都有什么事？": ("reminder_list", IntentEffect.READ),
        "查看今日日程": ("daily_agenda", IntentEffect.READ),
        "你好，介绍一下你自己": ("chat", IntentEffect.CHAT),
    }
    for text, result in expected.items():
        decision = decide_intent(text)
        assert (decision.intent, decision.effect) == result

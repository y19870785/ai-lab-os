from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.memory.models import MemoryQuery, MemoryType
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


def _settings(path):
    return make_test_settings(
        path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=0.01,
    )


async def _work_log_count(system) -> int:
    items = await system.memory_manager.retrieve_memory(
        MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=1000)
    )
    return sum(item.content.get("type") == "work_log" for item in items)


def _counts(client: TestClient, app) -> tuple[int, int, int]:
    return (
        len(client.get("/tasks").json()),
        client.get("/reminders?limit=100").json()["count"],
        client.portal.call(_work_log_count, app.state.system),
    )


@pytest.mark.parametrize("query", [
    "今天都有什么事？",
    "今天有什么事？",
    "今天都有哪些提醒？",
    "今天有什么提醒？",
    "我今天有什么要做的？",
    "接下来有什么提醒？",
])
def test_reminder_queries_are_read_only_across_real_composition(tmp_path, query):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        scheduled = client.post(
            "/chat", json={"user_input": "今天下午3点提醒我处理报价"}
        ).json()["metadata"]
        triggered = client.post(
            "/chat", json={"user_input": "今天下午4点提醒我联系张经理"}
        ).json()["metadata"]
        cancelled = client.post(
            "/chat", json={"user_input": "今天下午5点提醒我整理资料"}
        ).json()["metadata"]

        reminder = client.portal.call(
            app.state.system.reminder_service.get, triggered["reminder_id"]
        )
        client.portal.call(
            app.state.system.reminder_repository.trigger,
            reminder.id,
            reminder.remind_at,
            "intent-safety-test",
        )
        assert client.delete(f"/reminders/{cancelled['reminder_id']}").status_code == 200

        before = _counts(client, app)
        response = client.post("/chat", json={"user_input": query})
        after = _counts(client, app)

        assert response.status_code == 200
        body = response.json()
        assert body["metadata"]["intent"] == "reminder_list"
        assert body["metadata"]["effect"] == "read"
        assert before == after == (3, 3, 0)
        assert "MOCK MODE" not in body["answer"]
        assert "API_KEY" not in body["answer"]
        assert scheduled["reminder_id"] in body["answer"]


def test_explicit_work_log_still_writes_after_read_only_queries(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        before = _counts(client, app)
        question = client.post("/chat", json={"user_input": "今天都有什么事？"})
        after_question = _counts(client, app)
        written = client.post(
            "/chat", json={"user_input": "记录一下今天完成了报价审核"}
        )
        after_write = _counts(client, app)

        assert question.status_code == 200
        assert question.json()["metadata"]["effect"] == "read"
        assert before == after_question == (0, 0, 0)
        assert written.status_code == 200
        assert written.json()["metadata"]["intent"] == "work_log"
        assert written.json()["metadata"]["effect"] == "write"
        assert after_write == (0, 0, 1)


@pytest.mark.parametrize(
    ("text", "code", "message"),
    [
        ("查看提醒", "reminder.target_required", "请提供要查看的提醒标题"),
        ("取消提醒", "reminder.target_required", "请提供要取消的提醒标题"),
        ("把提醒改到明天下午4点", "reminder.target_required", "请提供要改期的提醒标题"),
        ("把提醒 rem_missing 改期", "reminder.time_required", "请提供新的提醒时间"),
        ("30分钟后提醒我开会", "reminder.time_unsupported", "今天下午3点"),
    ],
)
def test_chat_failure_contract_is_stable_chinese_and_side_effect_free(
    tmp_path, text, code, message
):
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        before = _counts(client, app)
        response = client.post("/chat", json={"user_input": text})
        after = _counts(client, app)

        assert response.status_code == 400
        assert response.json()["code"] == code
        assert message in response.json()["message"]
        assert before == after == (0, 0, 0)
        assert "MOCK MODE" not in response.text
        assert "API_KEY" not in response.text

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
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


def _workspace(name: str) -> dict[str, str]:
    return {"X-Tenant-ID": "tenant-a", "X-Workspace-ID": name}


def test_reminder_inbox_api_is_persisted_paginated_isolated_and_utf8(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        alpha = _workspace("alpha")
        first = client.post(
            "/chat", json={"user_input": "今天下午3点提醒我联系张经理"}, headers=alpha
        ).json()["metadata"]
        second = client.post(
            "/chat", json={"user_input": "明天下午3点提醒我整理报价"}, headers=alpha
        ).json()["metadata"]
        client.post(
            "/chat", json={"user_input": "明天下午4点提醒我不可见事项"},
            headers=_workspace("beta"),
        )

        page1 = client.get("/reminders?limit=1", headers=alpha)
        page2 = client.get("/reminders?limit=1&offset=1", headers=alpha)
        assert page1.status_code == 200
        assert "application/json" in page1.headers["content-type"]
        assert "charset=utf-8" in page1.headers["content-type"].lower()
        assert "联系张经理".encode("utf-8") in page1.content
        assert [item["reminder_id"] for item in page1.json()["items"]] == [
            first["reminder_id"]
        ]
        assert page1.json()["has_more"] is True
        assert [item["reminder_id"] for item in page2.json()["items"]] == [
            second["reminder_id"]
        ]
        assert page2.json()["has_more"] is False
        assert client.get("/reminders", headers=_workspace("beta")).json()["count"] == 1

        today = client.get("/reminders?time_scope=today", headers=alpha).json()
        assert [item["reminder_id"] for item in today["items"]] == [first["reminder_id"]]

    with TestClient(create_app(_settings(tmp_path), clock=clock)) as restarted:
        persisted = restarted.get("/reminders", headers=_workspace("alpha"))
        assert persisted.status_code == 200
        assert {item["reminder_id"] for item in persisted.json()["items"]} == {
            first["reminder_id"], second["reminder_id"],
        }


def test_reminder_inbox_status_filter_and_natural_language_query_are_read_only(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        created = client.post(
            "/chat", json={"user_input": "今天下午3点提醒我联系张经理"}
        ).json()["metadata"]
        before = client.get("/reminders").json()["count"]

        query = client.post("/chat", json={"user_input": "查看待触发提醒"})
        assert query.status_code == 200
        assert "charset=utf-8" in query.headers["content-type"].lower()
        assert "提醒列表".encode("utf-8") in query.content
        assert query.json()["metadata"]["intent"] == "reminder_list"
        assert query.json()["metadata"]["count"] == 1
        assert client.get("/reminders").json()["count"] == before

        today_query = client.post("/chat", json={"user_input": "查看今天的提醒"}).json()
        failed_query = client.post("/chat", json={"user_input": "查看失败提醒"}).json()
        all_query = client.post("/chat", json={"user_input": "查看我的提醒"}).json()
        assert today_query["metadata"]["filter"]["time_scope"] == "today"
        assert failed_query["metadata"]["filter"]["statuses"] == ["failed"]
        assert all_query["metadata"]["filter"]["statuses"] == []
        assert client.get("/reminders").json()["count"] == before

        reminder = client.portal.call(
            app.state.system.reminder_service.get, created["reminder_id"]
        )
        client.portal.call(
            app.state.system.reminder_repository.trigger,
            reminder.id,
            reminder.remind_at,
            "api-inbox-test",
        )
        triggered = client.get("/reminders?status=triggered").json()
        detail = client.get(f"/reminders/{created['reminder_id']}/status").json()
        assert triggered["count"] == 1
        assert triggered["items"][0]["status"] == detail["status"] == "triggered"
        assert triggered["items"][0]["occurrence_id"]
        assert client.get("/reminders?status=scheduled").json()["count"] == 0


def test_reminder_inbox_empty_cancelled_and_invalid_filters(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        empty = client.get("/reminders").json()
        assert empty["items"] == []
        assert empty["count"] == 0
        assert empty["has_more"] is False
        created = client.post(
            "/chat", json={"user_input": "明天下午3点提醒我联系张经理"}
        ).json()["metadata"]
        assert client.delete(f"/reminders/{created['reminder_id']}").status_code == 200
        cancelled = client.get("/reminders?status=cancelled").json()
        assert cancelled["count"] == 1
        assert cancelled["items"][0]["reminder_id"] == created["reminder_id"]
        assert client.get("/reminders?status=unknown").status_code == 400
        assert client.get("/reminders?limit=0").status_code == 400


def test_task_api_reminder_is_filtered_through_user_task_workspace(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        alpha = _workspace("alpha")
        task = client.post("/tasks", json={"title": "API workspace reminder"}, headers=alpha)
        created = client.post(
            f"/tasks/{task.json()['id']}/reminders",
            json={"remind_at": "2026-07-17T07:00:00Z", "timezone": "Asia/Shanghai"},
            headers=alpha,
        )
        assert created.status_code == 201
        updated = client.patch(
            f"/tasks/{task.json()['id']}",
            json={"metadata": {"workspace": {"workspace_id": "beta"}}},
            headers=alpha,
        )
        assert updated.status_code == 200
        assert updated.json()["metadata"]["workspace"]["workspace_id"] == "alpha"
        assert client.get("/reminders", headers=alpha).json()["count"] == 1
        assert client.get("/reminders", headers=_workspace("beta")).json()["count"] == 0

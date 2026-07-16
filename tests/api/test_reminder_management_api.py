from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


def _app(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc))
    settings = replace(make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=60,
    ), provider_mode="mock")
    return create_app(settings, clock=clock), clock


def _chat(client, text, headers=None):
    return client.post("/chat", json={"user_input": text}, headers=headers or {})


def test_pending_api_excludes_terminal_and_explicit_cancelled_upcoming_works(tmp_path):
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        scheduled = _chat(client, "明天下午3点提醒我整理报价").json()["metadata"]
        triggered = _chat(client, "明天下午4点提醒我联系张经理").json()["metadata"]
        cancelled = _chat(client, "明天下午5点提醒我取消验收").json()["metadata"]
        reminder = client.portal.call(
            app.state.system.reminder_service.get, triggered["reminder_id"]
        )
        client.portal.call(
            app.state.system.reminder_repository.trigger,
            reminder.id,
            reminder.remind_at,
            "api-management-trigger",
        )
        assert client.delete(f"/reminders/{cancelled['reminder_id']}").status_code == 200

        pending = client.get("/reminders?view=pending").json()
        explicit = client.get(
            "/reminders?status=cancelled&time_scope=upcoming"
        ).json()
        assert [item["reminder_id"] for item in pending["items"]] == [
            scheduled["reminder_id"]
        ]
        assert pending["filter"] == {
            "statuses": ["retrying", "scheduled"],
            "time_scope": "upcoming",
            "view": "pending",
        }
        assert [item["reminder_id"] for item in explicit["items"]] == [
            cancelled["reminder_id"]
        ]


def test_cancel_and_reschedule_api_are_idempotent_and_return_real_status(tmp_path):
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        cancel_target = _chat(client, "明天下午3点提醒我取消目标").json()["metadata"]
        first_cancel = client.delete(f"/reminders/{cancel_target['reminder_id']}")
        second_cancel = client.delete(f"/reminders/{cancel_target['reminder_id']}")
        assert first_cancel.json()["status"] == second_cancel.json()["status"] == "cancelled"

        target = _chat(client, "明天下午3点提醒我改期目标").json()["metadata"]
        headers = {"Idempotency-Key": "management-api-key"}
        body = {
            "scheduled_for": "2026-07-18T16:00:00+08:00",
            "timezone": "Asia/Shanghai",
        }
        changed = client.patch(
            f"/reminders/{target['reminder_id']}", json=body, headers=headers
        )
        repeated = client.patch(
            f"/reminders/{target['reminder_id']}", json=body, headers=headers
        )
        conflict = client.patch(
            f"/reminders/{target['reminder_id']}",
            json={**body, "scheduled_for": "2026-07-18T17:00:00+08:00"},
            headers=headers,
        )
        assert changed.status_code == repeated.status_code == 200
        assert changed.json()["scheduled_for"] == "2026-07-18T16:00:00+08:00"
        assert changed.json()["scheduler_job_id"] == target["scheduler_job_id"]
        assert repeated.json()["revision"] == changed.json()["revision"]
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "reminder.idempotency_conflict"


def test_management_api_enforces_workspace_and_terminal_state(tmp_path):
    app, _ = _app(tmp_path)
    alpha = {"X-Tenant-ID": "tenant-a", "X-Workspace-ID": "alpha"}
    beta = {"X-Tenant-ID": "tenant-a", "X-Workspace-ID": "beta"}
    with TestClient(app) as client:
        created = _chat(
            client, "明天下午3点提醒我隔离事项", headers=alpha
        ).json()["metadata"]
        reminder_id = created["reminder_id"]
        assert client.get(f"/reminders/{reminder_id}/status", headers=beta).status_code == 404
        assert client.delete(f"/reminders/{reminder_id}", headers=beta).status_code == 404

        reminder = client.portal.call(app.state.system.reminder_service.get, reminder_id)
        client.portal.call(
            app.state.system.reminder_repository.trigger,
            reminder.id,
            reminder.remind_at,
            "terminal-test",
        )
        terminal = client.patch(
            f"/reminders/{reminder_id}",
            json={
                "scheduled_for": "2026-07-18T17:00:00+08:00",
                "timezone": "Asia/Shanghai",
            },
            headers=alpha,
        )
        assert terminal.status_code == 409
        assert terminal.json()["code"] == "reminder.terminal_state"


def test_natural_language_management_is_deterministic_and_ambiguous_fails_closed(tmp_path):
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        first = _chat(client, "明天下午3点提醒我联系张经理").json()["metadata"]

        detail = _chat(client, f"查看提醒 {first['reminder_id']}")
        rescheduled = _chat(
            client, f"把提醒 {first['reminder_id']} 改到明天下午4点"
        )
        cancelled = _chat(client, f"取消提醒 {first['reminder_id']}")
        for response in (detail, rescheduled, cancelled):
            assert response.status_code == 200
            assert "MOCK MODE" not in response.text
            assert "OPENAI_API_KEY" not in response.text
            assert "real LLM" not in response.text

        _chat(client, "明天下午5点提醒我重复标题")
        _chat(client, "明天晚上8点提醒我重复标题")
        ambiguous = _chat(client, "取消重复标题的提醒")
        assert ambiguous.status_code == 409
        assert ambiguous.json()["code"] == "reminder.ambiguous"
        assert len(ambiguous.json()["details"]["candidates"]) == 2

        ordinary_chat = _chat(client, "你好，请简单介绍自己")
        assert ordinary_chat.status_code == 200
        assert "MOCK MODE" in ordinary_chat.json()["answer"]


def test_natural_language_pending_queries_are_read_only_and_noise_free(tmp_path):
    app, _ = _app(tmp_path)
    with TestClient(app) as client:
        _chat(client, "明天下午3点提醒我整理报价")
        cancelled = _chat(client, "明天下午4点提醒我取消事项").json()["metadata"]
        client.delete(f"/reminders/{cancelled['reminder_id']}")
        before = client.get("/reminders").json()["count"]

        for text in ("查看我的提醒", "查看待触发提醒", "查看待处理提醒", "接下来有什么提醒"):
            response = _chat(client, text)
            assert response.status_code == 200
            assert response.json()["metadata"]["filter"]["view"] == "pending"
            assert response.json()["metadata"]["count"] == 1
            assert "MOCK MODE" not in response.text
            assert "OPENAI_API_KEY" not in response.text
        assert client.get("/reminders").json()["count"] == before

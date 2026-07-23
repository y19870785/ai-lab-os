from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


def _settings(path, *, auth=False):
    settings = make_test_settings(
        path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=0.01,
    )
    if auth:
        settings = replace(settings, enable_api_auth=True, api_token="inbox-test-token-123456")
    return settings


def test_inbox_api_requires_existing_bearer_auth(tmp_path):
    with TestClient(create_app(_settings(tmp_path, auth=True))) as client:
        assert client.get("/inbox").status_code == 401
        response = client.get(
            "/inbox", headers={"Authorization": "Bearer inbox-test-token-123456"}
        )
        assert response.status_code == 200


def test_inbox_api_capture_read_resolve_and_dismiss(tmp_path):
    app = create_app(_settings(tmp_path), clock=MutableClock(NOW))
    with TestClient(app) as client:
        captures = [
            client.post("/inbox", json={"content": content}).json()
            for content in ("创建任务", "创建提醒", "记录完成", "保留想法", "丢弃内容")
        ]
        assert all(item["status"] == "pending" for item in captures)
        listed = client.get("/inbox").json()
        assert {item["id"] for item in listed["items"]} == {
            item["id"] for item in captures
        }

        task = client.post(
            f"/inbox/{captures[0]['id']}/resolve/task",
            json={"title": "跟进客户", "priority": "high"},
        )
        reminder = client.post(
            f"/inbox/{captures[1]['id']}/resolve/reminder",
            json={
                "title": "联系供应商",
                "scheduled_at": (NOW + timedelta(hours=3)).isoformat(),
                "timezone": "Asia/Shanghai",
            },
        )
        work_log = client.post(
            f"/inbox/{captures[2]['id']}/resolve/work-log",
            json={"title": "完成包装验货"},
        )
        note = client.post(f"/inbox/{captures[3]['id']}/resolve/note")
        dismissed = client.post(f"/inbox/{captures[4]['id']}/dismiss")

        assert task.status_code == reminder.status_code == work_log.status_code == 200
        assert task.json()["resolved_type"] == "user_task"
        assert reminder.json()["resolved_type"] == "reminder"
        assert work_log.json()["resolved_type"] == "work_log"
        assert note.json()["resolved_type"] == "note"
        assert dismissed.json()["status"] == "dismissed"
        assert client.get("/inbox").json()["items"] == []
        assert len(client.get("/inbox?status=all").json()["items"]) == 5


def test_inbox_api_failure_mapping_and_workspace_isolation(tmp_path, monkeypatch):
    app = create_app(_settings(tmp_path), clock=MutableClock(NOW))
    with TestClient(app) as client:
        assert client.post("/inbox", json={"content": "   "}).status_code == 400
        assert client.get("/inbox/inbox_missing").status_code == 404
        created = client.post(
            "/inbox",
            json={"content": "workspace protected"},
            headers={"X-Workspace-ID": "alpha"},
        ).json()
        mismatch = client.get(
            f"/inbox/{created['id']}", headers={"X-Workspace-ID": "beta"}
        )
        assert mismatch.status_code == 403

        resolved = client.post(f"/inbox/{created['id']}/resolve/note", headers={
            "X-Workspace-ID": "alpha"
        })
        assert resolved.status_code == 200
        conflict = client.post(f"/inbox/{created['id']}/resolve/note", headers={
            "X-Workspace-ID": "alpha"
        })
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "inbox.already_resolved"

        async def fail_get(*_args, **_kwargs):
            raise RuntimeError("SELECT secret FROM C:\\private\\inbox.db")

        monkeypatch.setattr(client.app.state.system.inbox_repository, "get", fail_get)
        internal = client.get("/inbox/inbox_any")
        assert internal.status_code == 500
        assert "select secret" not in internal.text.lower()
        assert "private" not in internal.text.lower()


def test_inbox_api_resolve_waiting_for_is_idempotent_and_scoped(tmp_path):
    app = create_app(_settings(tmp_path), clock=MutableClock(NOW))
    with TestClient(app) as client:
        captured = client.post(
            "/inbox",
            json={"content": "等张经理回复", "suggested_type": "waiting_for"},
            headers={"X-Workspace-ID": "alpha"},
        ).json()
        body = {
            "subject": "蜂蜡检测方案",
            "waiting_on": "张经理",
            "context": "等待确认",
            "next_review_at": (NOW + timedelta(days=1)).isoformat(),
            "timezone": "Asia/Shanghai",
        }
        path = f"/inbox/{captured['id']}/resolve/waiting-for"

        first = client.post(path, json=body, headers={"X-Workspace-ID": "alpha"})
        repeat = client.post(path, json=body, headers={"X-Workspace-ID": "alpha"})
        mismatch = client.post(path, json=body, headers={"X-Workspace-ID": "beta"})

        assert first.status_code == repeat.status_code == 200
        assert first.json()["resolved_type"] == "waiting_for"
        assert first.json()["resolved_target_id"].startswith("wf_inbox_")
        assert repeat.json()["resolved_target_id"] == first.json()["resolved_target_id"]
        assert mismatch.status_code == 403


def test_inbox_api_waiting_for_validation_fails_closed(tmp_path):
    app = create_app(_settings(tmp_path), clock=MutableClock(NOW))
    with TestClient(app) as client:
        captured = client.post("/inbox", json={"content": "等待确认"}).json()
        path = f"/inbox/{captured['id']}/resolve/waiting-for"

        missing_time = client.post(
            path,
            json={"subject": "方案", "waiting_on": "张经理"},
        )
        invalid_zone = client.post(
            path,
            json={
                "subject": "方案",
                "waiting_on": "张经理",
                "next_review_at": (NOW + timedelta(days=1)).isoformat(),
                "timezone": "Mars/Base",
            },
        )

        assert missing_time.status_code == 400
        assert missing_time.json()["code"] == "inbox.waiting_for.fields_missing"
        assert "confirmation_template" in missing_time.json()["details"]
        assert invalid_zone.status_code == 400
        assert invalid_zone.json()["code"] == "inbox.waiting_for.timezone_invalid"
        assert client.get(f"/inbox/{captured['id']}").json()["status"] == "pending"
        assert client.get("/waiting-for?view=all").json()["items"] == []


def test_inbox_api_waiting_for_timezone_uses_system_default_or_explicit_value(
    tmp_path,
):
    app = create_app(_settings(tmp_path), clock=MutableClock(NOW))
    with TestClient(app) as client:
        default_item = client.post(
            "/inbox", json={"content": "使用系统默认时区"}
        ).json()
        explicit_item = client.post(
            "/inbox", json={"content": "使用显式时区"}
        ).json()
        base_body = {
            "subject": "蜂蜡检测方案",
            "waiting_on": "张经理",
            "next_review_at": (NOW + timedelta(days=1)).isoformat(),
        }

        default_result = client.post(
            f"/inbox/{default_item['id']}/resolve/waiting-for",
            json=base_body,
        )
        explicit_result = client.post(
            f"/inbox/{explicit_item['id']}/resolve/waiting-for",
            json={**base_body, "timezone": "UTC"},
        )

        assert default_result.status_code == explicit_result.status_code == 200
        default_waiting = client.get(
            f"/waiting-for/{default_result.json()['resolved_target_id']}"
        ).json()
        explicit_waiting = client.get(
            f"/waiting-for/{explicit_result.json()['resolved_target_id']}"
        ).json()
        assert default_waiting["timezone"] == "Asia/Shanghai"
        assert explicit_waiting["timezone"] == "UTC"

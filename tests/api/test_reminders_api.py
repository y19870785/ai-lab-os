import asyncio
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from core.reminders.exceptions import ReminderUnavailableError


def _settings(tmp_path):
    return make_test_settings(
        tmp_path, enable_scheduler=True, enable_reminders=True
    )


def _future(seconds=3600):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def test_reminder_api_create_list_reschedule_cancel(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        task = client.post("/tasks", json={"title": "Follow up"}).json()
        created = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(),
            "timezone": "Asia/Shanghai",
        })
        assert created.status_code == 201
        reminder = created.json()
        assert reminder["id"].startswith("rem_")
        assert reminder["scheduler_job_id"]
        assert reminder["status"] == "scheduled"

        listed = client.get(f"/tasks/{task['id']}/reminders")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [reminder["id"]]

        changed = client.patch(f"/reminders/{reminder['id']}", json={
            "remind_at": _future(7200),
            "timezone": "UTC",
            "revision": reminder["revision"],
        })
        assert changed.status_code == 200
        assert changed.json()["revision"] > reminder["revision"]
        stale = client.patch(f"/reminders/{reminder['id']}", json={
            "remind_at": _future(9000),
            "timezone": "UTC",
            "revision": reminder["revision"],
        })
        assert stale.status_code == 409
        invalid_revision = client.patch(f"/reminders/{reminder['id']}", json={
            "remind_at": _future(9000), "timezone": "UTC", "revision": 0,
        })
        assert invalid_revision.status_code == 400

        cancelled = client.delete(f"/reminders/{reminder['id']}")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"


def test_reminder_api_validation_conflict_not_found_and_disabled(tmp_path):
    with TestClient(create_app(_settings(tmp_path / "enabled"))) as client:
        task = client.post("/tasks", json={"title": "Validate"}).json()
        naive = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": "2027-01-01T12:00:00", "timezone": "UTC",
        })
        assert naive.status_code == 400
        invalid_zone = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "Mars/Olympus",
        })
        assert invalid_zone.status_code == 400
        past = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": "2020-01-01T00:00:00Z", "timezone": "UTC",
        })
        assert past.status_code == 400
        missing = client.get("/reminders/rem_missing")
        assert missing.status_code == 404

        client.post(f"/tasks/{task['id']}/complete")
        terminal = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "UTC",
        })
        assert terminal.status_code == 409

    disabled = replace(
        make_test_settings(tmp_path / "disabled"),
        enable_reminders=True,
        enable_scheduler=False,
    )
    with TestClient(create_app(disabled)) as client:
        task = client.post("/tasks", json={"title": "No scheduler"}).json()
        response = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "UTC",
        })
        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "error"
        assert body["retryable"] is True
        assert set(body["details"]) <= {"reminder_id", "recovery_state"}


def test_triggered_reminder_api_exposes_one_occurrence_and_rejects_reschedule(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        task = client.post("/tasks", json={"title": "Trigger"}).json()
        created = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(1), "timezone": "UTC",
        }).json()
        system = client.app.state.system
        reminder = asyncio.run(system.reminder_service.get(created["id"]))
        asyncio.run(system.reminder_repository.trigger(
            reminder.id, reminder.remind_at, "api-test"
        ))
        asyncio.run(system.reminder_repository.trigger(
            reminder.id, reminder.remind_at, "api-test-repeat"
        ))

        occurrences = client.get(f"/reminders/{reminder.id}/occurrences")
        assert occurrences.status_code == 200
        assert len(occurrences.json()) == 1
        assert occurrences.json()[0]["status"] == "triggered"
        conflict = client.patch(f"/reminders/{reminder.id}", json={
            "remind_at": _future(7200), "timezone": "UTC",
        })
        assert conflict.status_code == 409


def test_running_reminder_job_reschedule_returns_409_without_state_change(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        task = client.post("/tasks", json={"title": "Running reminder"}).json()
        created = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "UTC",
        }).json()
        system = client.app.state.system
        job = asyncio.run(system.scheduler_runtime.get_job(created["scheduler_job_id"]))
        claim_now = datetime.fromisoformat(created["remind_at"]) + timedelta(seconds=1)
        asyncio.run(system.scheduler_runtime._persistence.claim_job(
            job.info.id,
            now=claim_now,
            claim_token="api-running-owner",
            claim_expires_at=claim_now + timedelta(minutes=1),
            run_id="api-running-run",
        ))

        response = client.patch(f"/reminders/{created['id']}", json={
            "remind_at": _future(7200),
            "timezone": "UTC",
            "revision": created["revision"],
        })
        stored = client.get(f"/reminders/{created['id']}").json()
        assert response.status_code == 409
        assert response.json()["code"] == "reminder.rescheduling_failed"
        assert response.json()["retryable"] is False
        assert stored["status"] == "scheduled"
        assert stored["remind_at"] == created["remind_at"]
        assert stored["revision"] == created["revision"]


def test_reminder_api_persistence_failure_is_sanitized_server_error(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        task = client.post("/tasks", json={"title": "Failure"}).json()

        async def broken_create(reminder):
            raise RuntimeError("SELECT secret FROM C:/private/reminders.db sk-private")

        client.app.state.system.reminder_repository.create = broken_create
        response = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "UTC",
        })
        assert response.status_code >= 500
        assert response.status_code != 400
        assert "select" not in response.text.lower()
        assert "private" not in response.text.lower()
        assert "sk-private" not in response.text.lower()


def test_task_complete_reports_partial_reminder_failure_and_retry_repairs(tmp_path):
    with TestClient(create_app(_settings(tmp_path))) as client:
        task = client.post("/tasks", json={"title": "Lifecycle API"}).json()
        reminder = client.post(f"/tasks/{task['id']}/reminders", json={
            "remind_at": _future(), "timezone": "UTC",
        }).json()
        bridge = client.app.state.system.reminder_bridge
        original_cancel = bridge.cancel
        attempts = 0

        async def fail_once(reminder_id, trace_id=""):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ReminderUnavailableError("injected lifecycle failure")
            return await original_cancel(reminder_id, trace_id)

        bridge.cancel = fail_once
        failed = client.post(f"/tasks/{task['id']}/complete")
        assert failed.status_code == 503
        assert failed.json()["component"] == "reminder_bridge"
        assert failed.json()["details"] == {
            "reminder_id": reminder["id"],
            "recovery_state": "pending_cancel",
        }
        assert client.get(f"/tasks/{task['id']}").json()["status"] == "completed"
        assert client.get(f"/reminders/{reminder['id']}").json()["status"] == "pending_cancel"

        repaired = client.post(f"/tasks/{task['id']}/complete")
        assert repaired.status_code == 200
        assert client.get(f"/reminders/{reminder['id']}").json()["status"] == "cancelled"

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

from api.app import create_app
from applications.models import ApplicationRequest
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


def _settings(path):
    return make_test_settings(
        path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=0.01,
    )


def _wait_for_status(client: TestClient, reminder_id: str, expected: str) -> dict:
    for _ in range(100):
        response = client.get(f"/reminders/{reminder_id}/status")
        assert response.status_code == 200
        body = response.json()
        if body["status"] == expected:
            return body
        time.sleep(0.01)
    raise AssertionError(f"Reminder did not reach {expected}: {body}")


def _wait_for_retry_count(client: TestClient, system, job_id: str, expected: int) -> None:
    for _ in range(100):
        job = client.portal.call(system.scheduler_runtime.get_job, job_id)
        if job.retry_count >= expected:
            return
        time.sleep(0.01)
    raise AssertionError(f"Scheduler job did not reach retry count {expected}")


def test_natural_language_reminder_persists_restarts_and_triggers_once(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    settings = _settings(tmp_path)
    request = {"user_input": "今天下午3点提醒我联系张经理确认蜂蜡检测方案"}
    headers = {"Idempotency-Key": "acceptance-request-001"}

    with TestClient(create_app(settings, clock=clock)) as client:
        created = client.post("/chat", json=request, headers=headers)
        assert created.status_code == 200
        metadata = created.json()["metadata"]
        assert metadata["intent"] == "reminder"
        assert metadata["task_id"].startswith("ut_nlr_")
        assert metadata["reminder_id"].startswith("rem_")
        assert metadata["scheduler_job_id"]
        assert metadata["reminder_status"] == "scheduled"
        assert metadata["scheduled_for"] == "2026-07-16T15:00:00+08:00"
        assert metadata["timezone"] == "Asia/Shanghai"
        reminder_id = metadata["reminder_id"]

        duplicate = client.post("/chat", json=request, headers=headers)
        assert duplicate.status_code == 200
        assert duplicate.json()["metadata"]["task_id"] == metadata["task_id"]
        assert duplicate.json()["metadata"]["reminder_id"] == reminder_id
        assert client.get(f"/reminders/{reminder_id}/status").json()["status"] == "scheduled"

    with TestClient(create_app(settings, clock=clock)) as client:
        persisted = client.get(f"/reminders/{reminder_id}/status")
        assert persisted.status_code == 200
        assert persisted.json()["status"] == "scheduled"
        clock.advance(timedelta(hours=1, minutes=1))
        triggered = _wait_for_status(client, reminder_id, "triggered")
        assert triggered["occurrence_id"]
        occurrences = client.get(f"/reminders/{reminder_id}/occurrences").json()
        assert len(occurrences) == 1
        assert occurrences[0]["status"] == "triggered"

    with TestClient(create_app(settings, clock=clock)) as client:
        assert client.get(f"/reminders/{reminder_id}/status").json()["status"] == "triggered"
        time.sleep(0.05)
        occurrences = client.get(f"/reminders/{reminder_id}/occurrences").json()
        assert len(occurrences) == 1


def test_task_only_does_not_require_reminder_components(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    with TestClient(create_app(make_test_settings(tmp_path), clock=clock)) as client:
        response = client.post("/chat", json={"user_input": "添加任务：联系张经理"})
        assert response.status_code == 200
        assert response.json()["metadata"]["metadata"]["intent"] == "task"
        assert response.json()["metadata"]["due_at"] is None


def test_api_rejects_unsupported_and_past_reminder_times(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        unsupported = client.post(
            "/chat", json={"user_input": "下周提醒我联系张经理"}
        )
        assert unsupported.status_code == 400
        assert unsupported.json()["code"] == "reminder.time_unsupported"
        past = client.post(
            "/chat", json={"user_input": "今天上午9点提醒我联系张经理"}
        )
        assert past.status_code == 400
        assert past.json()["code"] == "reminder.time_in_past"


def test_idempotency_key_cannot_be_reused_for_another_reminder(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    with TestClient(create_app(_settings(tmp_path), clock=clock)) as client:
        headers = {"Idempotency-Key": "same-key"}
        first = client.post(
            "/chat",
            json={"user_input": "今天下午3点提醒我联系张经理"},
            headers=headers,
        )
        assert first.status_code == 200
        conflict = client.post(
            "/chat",
            json={"user_input": "今天下午4点提醒我联系李经理"},
            headers=headers,
        )
        assert conflict.status_code == 409
        assert conflict.json()["code"] == "reminder.idempotency_conflict"


def test_cancelled_reminder_does_not_trigger_and_status_is_visible(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        created = client.post(
            "/chat",
            json={"user_input": "今天下午3点提醒我联系张经理"},
            headers={"Idempotency-Key": "cancel-request-001"},
        )
        reminder_id = created.json()["metadata"]["reminder_id"]
        cancelled = client.delete(f"/reminders/{reminder_id}")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"
        clock.advance(timedelta(hours=1, minutes=1))
        time.sleep(0.05)
        status = client.get(f"/reminders/{reminder_id}/status").json()
        assert status["status"] == "cancelled"
        assert client.get(f"/reminders/{reminder_id}/occurrences").json() == []


def test_reminder_disabled_fails_without_creating_task(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(make_test_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"user_input": "今天下午3点提醒我联系张经理"},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "reminder.unavailable"
        assert app.state.system.user_task_service is not None
        assert client.get("/tasks").json() == []


def test_trigger_failure_is_visible_and_never_reported_as_triggered(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        created = client.post(
            "/chat",
            json={"user_input": "今天下午3点提醒我联系张经理"},
            headers={"Idempotency-Key": "failure-request-001"},
        )
        assert created.status_code == 200
        metadata = created.json()["metadata"]
        system = app.state.system

        async def injected_failure(*_args, **_kwargs):
            raise RuntimeError("injected trigger failure")

        system.reminder_repository.trigger = injected_failure
        clock.advance(timedelta(hours=1, minutes=1))
        _wait_for_retry_count(client, system, metadata["scheduler_job_id"], 1)
        retrying = client.get(f"/reminders/{metadata['reminder_id']}/status").json()
        assert retrying["status"] == "retrying"
        assert retrying["last_failure"]["code"] == "reminders.trigger.failed"

        clock.advance(timedelta(seconds=2))
        _wait_for_retry_count(client, system, metadata["scheduler_job_id"], 2)
        clock.advance(timedelta(seconds=2))
        failed = _wait_for_status(client, metadata["reminder_id"], "failed")
        assert failed["status"] != "triggered"
        assert failed["retryable"] is True
        occurrences = client.get(
            f"/reminders/{metadata['reminder_id']}/occurrences"
        ).json()
        assert len(occurrences) == 1
        assert occurrences[0]["status"] == "failed"


def test_bridge_failure_is_not_reported_as_scheduled(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    app = create_app(_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        async def injected_schedule_failure(**_kwargs):
            raise FailureException(FailureInfo(
                code="reminders.bridge.schedule_failed",
                category=ErrorCategory.DEPENDENCY_FAILURE,
                message="Reminder schedule failed",
                component="reminder_bridge",
                operation="schedule",
                retryable=True,
                details={"reminder_id": "rem_recoverable"},
            ))

        app.state.system.reminder_bridge.create = injected_schedule_failure
        response = client.post(
            "/chat",
            json={"user_input": "今天下午3点提醒我联系张经理"},
            headers={"Idempotency-Key": "bridge-failure-001"},
        )
        assert response.status_code != 200
        assert response.json()["code"] == "reminder.scheduling_failed"
        tasks = client.get("/tasks").json()
        assert len(tasks) == 1
        assert tasks[0]["metadata"]["scheduling_status"] == "failed"
        assert "已安排" not in response.text


@pytest.mark.asyncio
async def test_concurrent_idempotent_retries_create_one_reminder(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    system = await create_system(_settings(tmp_path), clock=clock)
    await system.start()
    try:
        requests = [
            ApplicationRequest(
                application_name="ceo-assistant",
                user_input="今天下午3点提醒我联系张经理",
                workspace_key=WorkspaceKey(trace_id=f"trace-{index}"),
                metadata={"idempotency_key": "concurrent-request-001"},
            )
            for index in range(2)
        ]
        first, second = await asyncio.gather(*(
            system.application_runtime.execute(request) for request in requests
        ))
        assert first.metadata["task_id"] == second.metadata["task_id"]
        assert first.metadata["reminder_id"] == second.metadata["reminder_id"]
        reminders = await system.reminder_service.list_for_task(
            first.metadata["task_id"]
        )
        assert len(reminders) == 1
    finally:
        await system.shutdown()

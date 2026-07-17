from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from core.time_utils import parse_iso_timestamp

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock


async def _tick_and_settle(system):
    await system.scheduler_runtime._tick()
    tasks = list(system.scheduler_runtime._background_tasks)
    if tasks:
        await asyncio.gather(*tasks)
    await asyncio.sleep(0)


def test_cancel_and_reschedule_survive_restart_and_trigger_effectively_once(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc))
    settings = make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=60,
    )
    old_due = clock.now() + timedelta(hours=1)
    new_due = clock.now() + timedelta(hours=2)

    with TestClient(create_app(settings, clock=clock)) as client:
        cancelled = client.post(
            "/chat", json={"user_input": "今天上午9点提醒我取消后不触发"}
        ).json()["metadata"]
        rescheduled = client.post(
            "/chat", json={"user_input": "今天上午9点提醒我改期后触发"}
        ).json()["metadata"]
        cancel_response = client.post(
            "/chat", json={"user_input": f"取消提醒 {cancelled['reminder_id']}"}
        )
        patch_response = client.patch(
            f"/reminders/{rescheduled['reminder_id']}",
            json={
                "scheduled_for": new_due.isoformat(),
                "timezone": "Asia/Shanghai",
            },
            headers={"Idempotency-Key": "integration-reschedule"},
        )
        assert cancel_response.status_code == patch_response.status_code == 200
        assert patch_response.json()["scheduler_job_id"] == rescheduled["scheduler_job_id"]
        assert parse_iso_timestamp(rescheduled["scheduled_for"]) == old_due

    with TestClient(create_app(settings, clock=clock)) as restarted:
        cancel_status = restarted.get(
            f"/reminders/{cancelled['reminder_id']}/status"
        ).json()
        changed_status = restarted.get(
            f"/reminders/{rescheduled['reminder_id']}/status"
        ).json()
        assert cancel_status["status"] == "cancelled"
        assert parse_iso_timestamp(changed_status["scheduled_for"]) == new_due

        clock.advance(timedelta(hours=1, minutes=30))
        restarted.portal.call(_tick_and_settle, restarted.app.state.system)
        assert restarted.get(
            f"/reminders/{cancelled['reminder_id']}/occurrences"
        ).json() == []
        assert restarted.get(
            f"/reminders/{rescheduled['reminder_id']}/occurrences"
        ).json() == []

        clock.advance(timedelta(hours=1))
        restarted.portal.call(_tick_and_settle, restarted.app.state.system)
        occurrences = restarted.get(
            f"/reminders/{rescheduled['reminder_id']}/occurrences"
        ).json()
        restarted.portal.call(_tick_and_settle, restarted.app.state.system)
        assert len(occurrences) == 1
        assert restarted.get(
            f"/reminders/{rescheduled['reminder_id']}/status"
        ).json()["status"] == "triggered"
        assert len(restarted.get(
            f"/reminders/{rescheduled['reminder_id']}/occurrences"
        ).json()) == 1

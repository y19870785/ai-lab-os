"""Real-container Daily Review aggregation, isolation, and zero-side-effect proof."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from tests.helpers.clock import MutableClock

LOCAL = {
    "X-Tenant-ID": "tenant-local",
    "X-Workspace-ID": "workspace-shared",
    "X-Namespace": "operations",
}
FOREIGN = {
    "X-Tenant-ID": "tenant-foreign",
    "X-Workspace-ID": "workspace-shared",
    "X-Namespace": "operations",
}


def _database_snapshot(sqlite_dir: Path) -> dict[str, dict[str, list[tuple]]]:
    snapshot: dict[str, dict[str, list[tuple]]] = {}
    for path in sorted(sqlite_dir.glob("*.db")):
        with sqlite3.connect(path) as connection:
            tables = [
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' ORDER BY name"
                )
            ]
            snapshot[path.name] = {
                table: connection.execute(
                    f'SELECT * FROM "{table}" ORDER BY rowid'
                ).fetchall()
                for table in tables
            }
    return snapshot


def _create_source_snapshot(client: TestClient, headers: dict[str, str]):
    work_log = client.post(
        "/work-logs",
        headers=headers,
        json={
            "subject": f"Fact {headers['X-Tenant-ID']}",
            "raw_text": "canonical fact",
            "occurred_at": "2026-07-27T10:00:00Z",
            "timezone": "UTC",
            "status": "completed",
        },
    )
    assert work_log.status_code == 200

    due_task = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": f"Due task {headers['X-Tenant-ID']}",
            "due_at": "2026-07-27T13:00:00Z",
            "timezone": "UTC",
        },
    )
    assert due_task.status_code == 201

    reminder_task = client.post(
        "/tasks",
        headers=headers,
        json={"title": f"Reminder task {headers['X-Tenant-ID']}"},
    )
    assert reminder_task.status_code == 201
    reminder = client.post(
        f"/tasks/{reminder_task.json()['id']}/reminders",
        headers=headers,
        json={
            "remind_at": "2026-07-27T14:00:00Z",
            "timezone": "UTC",
        },
    )
    assert reminder.status_code == 201

    waiting = client.post(
        "/waiting-for",
        headers=headers,
        json={
            "subject": f"Waiting {headers['X-Tenant-ID']}",
            "waiting_on": "external",
            "expected_by": "2026-07-27T11:00:00Z",
            "timezone": "UTC",
        },
    )
    assert waiting.status_code == 201

    inbox = client.post(
        "/inbox",
        headers=headers,
        json={"content": f"Inbox {headers['X-Tenant-ID']}"},
    )
    assert inbox.status_code == 201

    return {
        work_log.json()["id"],
        due_task.json()["id"],
        reminder.json()["id"],
        waiting.json()["item"]["id"],
        inbox.json()["id"],
    }


def _all_item_ids(review: dict) -> list[str]:
    return [
        item["source_id"]
        for section in (
            "blocked",
            "follow_ups",
            "in_progress",
            "completed",
            "informational",
            "pending_inbox",
        )
        for item in review[section]["items"]
    ]


def test_real_sources_api_ceo_restart_and_zero_side_effects(tmp_path):
    settings = make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="UTC",
    )
    clock = MutableClock(datetime(2026, 7, 27, 12, tzinfo=UTC))
    first_structured: dict

    with TestClient(create_app(settings, clock=clock)) as client:
        local_ids = _create_source_snapshot(client, LOCAL)
        foreign_ids = _create_source_snapshot(client, FOREIGN)
        system = client.app.state.system
        published = []

        async def capture(event):
            published.append(event)

        system.event_bus.add_after_publish_hook(capture)

        async def provider_bomb(*args, **kwargs):
            raise AssertionError("Daily Review must not call a Provider")

        system.llm_provider.generate = provider_bomb
        before = _database_snapshot(settings.sqlite_dir)

        api_default = client.get(
            "/daily-review",
            params={"date": "today"},
            headers=LOCAL,
        )
        api_explicit = client.get(
            "/daily-review",
            params={"date": "today", "limit": 50, "offset": 0},
            headers=LOCAL,
        )
        ceo = client.get("/brief", headers=LOCAL)
        after = _database_snapshot(settings.sqlite_dir)

        assert api_default.status_code == api_explicit.status_code == 200
        assert ceo.status_code == 200
        first_structured = api_default.json()
        assert api_explicit.json() == first_structured
        assert ceo.json()["metadata"]["daily_review"] == first_structured
        assert set(_all_item_ids(first_structured)) == local_ids
        assert foreign_ids.isdisjoint(_all_item_ids(first_structured))
        assert first_structured["page"]["total_count"] == 5
        assert before == after
        assert published == []

    with TestClient(create_app(settings, clock=clock)) as client:
        restarted = client.get(
            "/daily-review",
            params={"date": "today"},
            headers=LOCAL,
        )

    assert restarted.status_code == 200
    assert restarted.json() == first_structured

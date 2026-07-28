"""Real-container Daily Review aggregation, isolation, and zero-side-effect proof."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from applications.models import ApplicationRequest
from core.daily_review import DailyReviewQuery
from core.errors import ErrorCategory, FailureException
from core.system import make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock

LOCAL = {
    "X-Tenant-ID": "tenant-a",
    "X-Workspace-ID": "workspace-a",
    "X-Namespace": "namespace-a",
}
FOREIGN_TENANT = {
    "X-Tenant-ID": "tenant-b",
    "X-Workspace-ID": "workspace-a",
    "X-Namespace": "namespace-a",
}
FOREIGN_WORKSPACE = {
    "X-Tenant-ID": "tenant-a",
    "X-Workspace-ID": "workspace-b",
    "X-Namespace": "namespace-a",
}
FOREIGN_NAMESPACE = {
    "X-Tenant-ID": "tenant-a",
    "X-Workspace-ID": "workspace-a",
    "X-Namespace": "namespace-b",
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
    scope = "/".join((
        headers["X-Tenant-ID"],
        headers["X-Workspace-ID"],
        headers["X-Namespace"],
    ))
    work_log = client.post(
        "/work-logs",
        headers=headers,
        json={
            "subject": f"Fact {scope}",
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
            "title": f"Due task {scope}",
            "due_at": "2026-07-27T13:00:00Z",
            "timezone": "UTC",
        },
    )
    assert due_task.status_code == 201

    reminder_task = client.post(
        "/tasks",
        headers=headers,
        json={"title": f"Reminder task {scope}"},
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
            "subject": f"Waiting {scope}",
            "waiting_on": "external",
            "expected_by": "2026-07-27T11:00:00Z",
            "timezone": "UTC",
        },
    )
    assert waiting.status_code == 201

    inbox = client.post(
        "/inbox",
        headers=headers,
        json={"content": f"Inbox {scope}"},
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


def _section_totals(review: dict) -> dict[str, int]:
    return {
        section: review[section]["section_total_count"]
        for section in (
            "blocked",
            "follow_ups",
            "in_progress",
            "completed",
            "informational",
            "pending_inbox",
        )
    }


def _workspace(headers: dict[str, str]) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=headers["X-Tenant-ID"],
        workspace_id=headers["X-Workspace-ID"],
        namespace=headers["X-Namespace"],
        trace_id=headers.get("X-Trace-ID", ""),
    )


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
        ids_by_scope = {
            "local": _create_source_snapshot(client, LOCAL),
            "foreign_tenant": _create_source_snapshot(
                client,
                FOREIGN_TENANT,
            ),
            "foreign_workspace": _create_source_snapshot(
                client,
                FOREIGN_WORKSPACE,
            ),
            "foreign_namespace": _create_source_snapshot(
                client,
                FOREIGN_NAMESPACE,
            ),
        }
        local_ids = ids_by_scope["local"]
        foreign_ids = set().union(
            ids_by_scope["foreign_tenant"],
            ids_by_scope["foreign_workspace"],
            ids_by_scope["foreign_namespace"],
        )
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

        assert api_default.status_code == api_explicit.status_code == 200
        assert ceo.status_code == 200
        first_structured = api_default.json()
        assert api_explicit.json() == first_structured
        assert ceo.json()["metadata"]["daily_review"] == first_structured
        assert set(_all_item_ids(first_structured)) == local_ids
        assert foreign_ids.isdisjoint(_all_item_ids(first_structured))
        assert first_structured["page"]["total_count"] == 5
        assert first_structured["page"]["has_more"] is False
        assert _section_totals(first_structured) == {
            "blocked": 0,
            "follow_ups": 3,
            "in_progress": 0,
            "completed": 1,
            "informational": 0,
            "pending_inbox": 1,
        }
        local_tail = client.get(
            "/daily-review",
            params={"date": "today", "limit": 1, "offset": 4},
            headers=LOCAL,
        ).json()
        assert local_tail["page"] == {
            "count": 1,
            "total_count": 5,
            "limit": 1,
            "offset": 4,
            "has_more": False,
        }
        assert set(_all_item_ids(local_tail)).issubset(local_ids)
        assert foreign_ids.isdisjoint(_all_item_ids(local_tail))
        for name, headers in (
            ("foreign_tenant", FOREIGN_TENANT),
            ("foreign_workspace", FOREIGN_WORKSPACE),
            ("foreign_namespace", FOREIGN_NAMESPACE),
        ):
            scoped = client.get(
                "/daily-review",
                params={"date": "today"},
                headers=headers,
            )
            assert scoped.status_code == 200
            scoped_review = scoped.json()
            assert set(_all_item_ids(scoped_review)) == ids_by_scope[name]
            assert scoped_review["page"]["total_count"] == 5
            assert scoped_review["page"]["has_more"] is False
            assert _section_totals(scoped_review) == _section_totals(
                first_structured
            )
        after = _database_snapshot(settings.sqlite_dir)
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


def test_api_brief_and_ceo_source_failure_contracts_are_identical(tmp_path):
    settings = make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="UTC",
    )
    clock = MutableClock(datetime(2026, 7, 27, 12, tzinfo=UTC))
    headers = {
        **LOCAL,
        "X-Trace-ID": "trace-daily-review-parity",
    }

    with TestClient(create_app(settings, clock=clock)) as client:
        system = client.app.state.system

        async def fail_work_log(*args, **kwargs):
            raise RuntimeError("private source failure")

        system.work_log_service.list = fail_work_log
        api_response = client.get(
            "/daily-review",
            params={"date": "today"},
            headers=headers,
        )
        brief_response = client.get("/brief", headers=headers)

        workspace = _workspace(headers)
        with pytest.raises(FailureException) as service_exc:
            asyncio.run(system.daily_review.get(
                workspace_key=workspace,
                query=DailyReviewQuery(review_date="today"),
            ))
        with pytest.raises(FailureException) as ceo_exc:
            asyncio.run(system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input="今日简报",
                    workspace_key=workspace,
                ),
            ))

    assert api_response.status_code == brief_response.status_code == 503
    observable_fields = (
        "code",
        "component",
        "retryable",
        "details",
        "trace_id",
    )
    assert {
        field: api_response.json()[field]
        for field in observable_fields
    } == {
        field: brief_response.json()[field]
        for field in observable_fields
    } == {
        "code": "daily_review.source_failed",
        "component": "daily_review",
        "retryable": True,
        "details": {
            "source": "work_log",
            "upstream_code": "work_log.unhandled_failure",
            "upstream_category": "internal",
        },
        "trace_id": "trace-daily-review-parity",
    }
    service_failure = service_exc.value.failure
    ceo_failure = ceo_exc.value.failure
    assert service_failure == ceo_failure
    assert service_failure.category == ErrorCategory.DEPENDENCY_FAILURE
    assert service_failure.operation == "get"

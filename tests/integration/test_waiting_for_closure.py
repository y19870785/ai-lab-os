"""End-to-end Waiting-For persistence, API and Agenda closure."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system import create_system, make_test_settings
from core.system.exceptions import SystemInitializationError
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 22, 8, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_waiting_for_survives_restart_and_feeds_agenda_without_reminders(tmp_path):
    settings = make_test_settings(
        tmp_path, enable_reminders=False, enable_scheduler=False
    )
    workspace = WorkspaceKey(workspace_id="alpha")
    clock = MutableClock(NOW)
    first = await create_system(settings, clock=clock)
    await first.start()
    created = await first.waiting_for_service.create(
        workspace_key=workspace,
        subject="等待包装供应商确认",
        waiting_on="包装供应商",
        next_review_at=NOW - timedelta(minutes=1),
        timezone="Asia/Shanghai",
        source="integration",
    )
    attention = await first.daily_agenda.list(
        workspace_key=workspace, view="attention"
    )
    assert attention.items[0].waiting_for_id == created.item.id
    assert attention.items[0].kind.value == "attention"
    await first.shutdown()

    second = await create_system(settings, clock=clock)
    await second.start()
    restored = await second.waiting_for_service.get(
        workspace_key=workspace, waiting_for_id=created.item.id
    )
    assert restored.subject == "等待包装供应商确认"
    resolved = await second.waiting_for_service.resolve(
        workspace_key=workspace,
        waiting_for_id=restored.id,
        expected_revision=restored.revision,
        resolution_note="供应商已确认",
        source="integration",
    )
    assert resolved.item.status.value == "resolved"
    assert (
        await second.waiting_for_service.list_events(
            workspace_key=workspace, waiting_for_id=restored.id
        )
    ).items[-1].event_type.value == "resolved"
    await second.shutdown()


def test_real_application_api_is_workspace_scoped_and_uses_canonical_service(tmp_path):
    settings = make_test_settings(tmp_path)
    with TestClient(create_app(settings, clock=MutableClock(NOW))) as client:
        created = client.post(
            "/waiting-for",
            headers={"X-Workspace-ID": "alpha"},
            json={"subject": "Legal reply", "waiting_on": "Counsel"},
        )
        assert created.status_code == 201
        item_id = created.json()["item"]["id"]
        assert client.get(
            f"/waiting-for/{item_id}", headers={"X-Workspace-ID": "alpha"}
        ).status_code == 200
        hidden = client.get(
            f"/waiting-for/{item_id}", headers={"X-Workspace-ID": "beta"}
        )
        assert hidden.status_code == 404
        assert "Legal reply" not in hidden.text
        assert client.app.state.system.waiting_for_service is not None


def test_real_application_api_explicit_id_retry_creates_one_chain(tmp_path):
    settings = make_test_settings(tmp_path)
    headers = {"X-Workspace-ID": "alpha"}
    body = {
        "waiting_for_id": "wf_retry_boundary",
        "subject": "Retry boundary",
        "waiting_on": "Counsel",
    }
    with TestClient(create_app(settings, clock=MutableClock(NOW))) as client:
        first = client.post("/waiting-for", headers=headers, json=body)
        retry = client.post("/waiting-for", headers=headers, json=body)
        assert first.status_code == 201
        assert first.json()["item"]["id"] == "wf_retry_boundary"
        assert retry.status_code == 409

        listed = client.get("/waiting-for", headers=headers).json()["items"]
        history = client.get(
            "/waiting-for/wf_retry_boundary/events", headers=headers
        ).json()["items"]
        assert [item["id"] for item in listed] == ["wf_retry_boundary"]
        assert [(event["sequence"], event["event_type"]) for event in history] == [
            (1, "created")
        ]


@pytest.mark.asyncio
async def test_waiting_for_initialization_failure_rolls_back_system_start(tmp_path, monkeypatch):
    system = await create_system(make_test_settings(tmp_path))

    async def fail_initialize():
        raise RuntimeError("injected followups.db initialization failure")

    monkeypatch.setattr(system.waiting_for_service, "initialize", fail_initialize)
    with pytest.raises(SystemInitializationError):
        await system.start()
    assert not system.accepting_work
    assert not system.event_bus.is_running

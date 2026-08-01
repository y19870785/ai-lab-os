"""Complete WorkspaceKey and fail-closed header contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings


@pytest.mark.parametrize(
    "header",
    [
        "X-Tenant-ID",
        "X-Workspace-ID",
        "X-Namespace",
        "X-Session-ID",
        "X-Agent-ID",
    ],
)
def test_blank_workspace_header_fails_before_business_access(tmp_path, header):
    with TestClient(create_app(make_test_settings(tmp_path))) as client:
        response = client.post(
            "/tasks",
            headers={header: "   "},
            json={"title": "must not persist"},
        )
        assert response.status_code == 400
        assert response.json()["code"] == "workspace.header_invalid"
        assert response.json()["details"]["header"] == header
        assert client.get("/tasks").json() == []


def test_missing_headers_use_profile_defaults_and_valid_headers_override(tmp_path):
    settings = replace(
        make_test_settings(tmp_path),
        workspace_tenant_id="profile-tenant",
        workspace_id="profile-workspace",
        workspace_namespace="profile-namespace",
        workspace_session_id="profile-session",
        workspace_agent_id="profile-agent",
    )
    with TestClient(create_app(settings)) as client:
        created = client.post("/tasks", json={"title": "profile task"})
        assert created.status_code == 201
        assert len(client.get("/tasks").json()) == 1
        assert client.get(
            "/tasks",
            headers={"X-Workspace-ID": "other-workspace"},
        ).json() == []


def test_chat_body_session_override_and_context_fallback_are_complete(tmp_path):
    settings = replace(
        make_test_settings(tmp_path),
        workspace_tenant_id="profile-tenant",
        workspace_id="profile-workspace",
        workspace_namespace="profile-namespace",
        workspace_session_id="profile-session",
        workspace_agent_id="profile-agent",
    )
    app = create_app(settings)
    with TestClient(app) as client:
        first = client.post(
            "/chat",
            headers={"X-Trace-ID": "chat-body-session"},
            json={"user_input": "你好", "session_id": "body-session"},
        )
        assert first.status_code == 200
        body_context = app.state.system.application_runtime.get_context(
            "chat-body-session"
        )
        assert body_context.workspace_key.model_dump() == {
            "tenant_id": "profile-tenant",
            "workspace_id": "profile-workspace",
            "namespace": "profile-namespace",
            "user_id": "",
            "session_id": "body-session",
            "agent_id": "profile-agent",
            "trace_id": "chat-body-session",
        }

        second = client.post(
            "/chat",
            headers={
                "X-Trace-ID": "chat-header-session",
                "X-Session-ID": "header-session",
                "X-Agent-ID": "header-agent",
            },
            json={"user_input": "你好", "session_id": "   "},
        )
        assert second.status_code == 200
        header_context = app.state.system.application_runtime.get_context(
            "chat-header-session"
        )
        assert header_context.session_id == "header-session"
        assert header_context.workspace_key.agent_id == "header-agent"


def test_brief_uses_session_and_agent_from_shared_context(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    headers = {
        "X-Trace-ID": "brief-context",
        "X-Tenant-ID": "tenant",
        "X-Workspace-ID": "workspace",
        "X-Namespace": "operations",
        "X-Session-ID": "session",
        "X-Agent-ID": "agent",
    }
    with TestClient(app) as client:
        response = client.get("/brief", headers=headers)
        assert response.status_code == 200
        key = app.state.system.application_runtime.get_context(
            "brief-context"
        ).workspace_key
        assert (
            key.tenant_id,
            key.workspace_id,
            key.namespace,
            key.session_id,
            key.agent_id,
        ) == ("tenant", "workspace", "operations", "session", "agent")


def test_same_context_flows_through_agenda_review_hint_and_mutation(tmp_path):
    headers = {
        "X-Tenant-ID": "tenant",
        "X-Workspace-ID": "workspace",
        "X-Namespace": "operations",
        "X-Session-ID": "session",
        "X-Agent-ID": "agent",
    }
    with TestClient(create_app(make_test_settings(tmp_path))) as client:
        created = client.post(
            "/tasks",
            headers=headers,
            json={
                "title": "Shared context overdue",
                "due_at": (
                    datetime.now(UTC) - timedelta(hours=1)
                ).isoformat(),
            },
        ).json()
        agenda = client.get("/agenda", headers=headers)
        review = client.get(
            "/daily-review?date=today",
            headers=headers,
        )
        hints = client.get(
            "/daily-review/action-hints?date=today",
            headers=headers,
        )
        assert agenda.status_code == review.status_code == hints.status_code == 200
        assert created["id"] in agenda.text
        assert created["id"] in review.text
        assert any(
            hint["source_id"] == created["id"]
            for hint in hints.json()
        )
        completed = client.post(
            f"/daily-review/actions/user-tasks/{created['id']}/complete",
            headers=headers,
            json={"expected_revision": created["revision"]},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert client.get(
            "/tasks",
            headers={**headers, "X-Workspace-ID": "isolated"},
        ).json() == []

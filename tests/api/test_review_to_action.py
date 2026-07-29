"""Review-to-Action UserTask revision and workspace safety."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings


def test_review_user_task_complete_requires_caller_revision(tmp_path):
    with TestClient(create_app(make_test_settings(tmp_path))) as client:
        created = client.post("/tasks", json={"title": "Close from review"}).json()
        path = f"/daily-review/actions/user-tasks/{created['id']}/complete"

        missing = client.post(path, json={})
        assert missing.status_code == 400
        stale = client.post(path, json={"expected_revision": 99})
        assert stale.status_code == 409
        completed = client.post(
            path,
            json={"expected_revision": created["revision"]},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert completed.json()["revision"] == created["revision"] + 1
        assert completed.json()["metadata"] == {}
        assert "legacy_source_id" not in completed.json()
        assert completed.json()["overdue"] is False

        stale_terminal = client.post(
            path,
            json={"expected_revision": created["revision"]},
        )
        assert stale_terminal.status_code == 409
        exact_terminal = client.post(
            path,
            json={"expected_revision": completed.json()["revision"]},
        )
        assert exact_terminal.status_code == 200
        assert exact_terminal.json()["revision"] == completed.json()["revision"]


def test_review_user_task_cancel_is_workspace_scoped_and_compatible(tmp_path):
    with TestClient(create_app(make_test_settings(tmp_path))) as client:
        headers = {
            "X-Tenant-ID": "tenant-a",
            "X-Workspace-ID": "workspace-a",
            "X-Namespace": "daily",
            "X-Session-ID": "session-a",
            "X-Agent-ID": "agent-a",
        }
        created = client.post(
            "/tasks",
            json={"title": "Cancel from review"},
            headers=headers,
        ).json()
        path = f"/daily-review/actions/user-tasks/{created['id']}/cancel"
        denied = client.post(
            path,
            json={"expected_revision": created["revision"]},
            headers={**headers, "X-Workspace-ID": "workspace-b"},
        )
        assert denied.status_code == 404
        cancelled = client.post(
            path,
            json={"expected_revision": created["revision"]},
            headers=headers,
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        compatible = client.post(
            "/tasks",
            json={"title": "Historical API compatibility"},
        ).json()
        assert client.post(f"/tasks/{compatible['id']}/complete").status_code == 200


def test_review_action_preserves_overdue_before_terminal_transition(tmp_path):
    with TestClient(create_app(make_test_settings(tmp_path))) as client:
        created = client.post(
            "/tasks",
            json={
                "title": "Overdue task",
                "due_at": (
                    datetime.now(UTC) - timedelta(days=1)
                ).isoformat(),
            },
        ).json()
        response = client.post(
            f"/daily-review/actions/user-tasks/{created['id']}/cancel",
            json={"expected_revision": created["revision"]},
        )
        assert response.status_code == 200
        assert response.json()["overdue"] is False

from dataclasses import replace

from fastapi.testclient import TestClient

from api.app import create_app
from core.system import make_test_settings
from core.user_tasks.exceptions import UserTaskPersistenceError


def test_real_user_task_api_and_persistence(tmp_path):
    settings = make_test_settings(tmp_path)
    app = create_app(settings)
    with TestClient(app) as client:
        created = client.post("/tasks", json={"title": "Call customer", "priority": "high"})
        assert created.status_code == 201
        task_id = created.json()["id"]
        assert task_id.startswith("ut_") and task_id != "task-001"
        assert client.get(f"/tasks/{task_id}").json()["title"] == "Call customer"
        assert client.get("/tasks", params={"status": "active"}).json()[0]["id"] == task_id
        updated = client.patch(f"/tasks/{task_id}", json={"title": "Call key customer"})
        assert updated.status_code == 200 and updated.json()["revision"] == 2
    with TestClient(create_app(settings)) as client:
        completed = client.post(f"/tasks/{task_id}/complete")
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/tasks/{task_id}").json()["status"] == "completed"
        assert client.post(f"/tasks/{task_id}/cancel").status_code == 409


def test_user_task_api_validation_not_found_and_no_internal_leak(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        invalid = client.post("/tasks", json={"title": "   "})
        assert invalid.status_code == 400
        missing = client.get("/tasks/ut_missing")
        assert missing.status_code == 404
        body = missing.json()
        assert {"status", "code", "message", "component", "retryable", "trace_id", "details"} <= body.keys()
        assert "sqlite" not in missing.text.lower()
        assert "select " not in missing.text.lower()


def test_user_task_api_database_failure_and_disabled_service_are_non_2xx(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        async def fail_create(task):
            raise UserTaskPersistenceError("SELECT secret FROM C:\\private\\tasks.db")

        client.app.state.system.user_task_repository.create = fail_create
        response = client.post("/tasks", json={"title": "must fail"})
        assert response.status_code >= 500
        assert response.json()["status"] == "error"
        assert response.json()["component"] == "user_tasks"
        assert "select" not in response.text.lower()
        assert "private" not in response.text.lower()

    disabled = replace(
        make_test_settings(tmp_path / "disabled"), enable_user_tasks=False
    )
    with TestClient(create_app(disabled)) as client:
        response = client.post("/tasks", json={"title": "must not mock"})
        assert response.status_code >= 400
        assert response.json()["code"] == "user_tasks.disabled"

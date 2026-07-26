import inspect
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from api.app import create_app
from api.routes import tasks as task_routes
from core.system import make_test_settings
from core.user_tasks.exceptions import UserTaskPersistenceError
from tests.helpers.clock import MutableClock


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
        invalid_zone = client.post("/tasks", json={
            "title": "bad zone", "timezone": "Mars/Olympus_Mons",
        })
        assert invalid_zone.status_code == 400

        created = client.post("/tasks", json={"title": "revision guard"})
        task_id = created.json()["id"]
        for revision in (0, -1):
            invalid_revision = client.patch(
                f"/tasks/{task_id}", json={"title": "must fail", "revision": revision}
            )
            assert invalid_revision.status_code == 400
        stale = client.patch(
            f"/tasks/{task_id}", json={"title": "stale", "revision": 99}
        )
        assert stale.status_code == 409


def test_user_task_list_datetime_filters_use_validation_contract_and_utc(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        created = client.post("/tasks", json={
            "title": "timezone query",
            "due_at": "2026-07-16T15:00:00+08:00",
            "timezone": "Asia/Shanghai",
        })
        assert created.status_code == 201

        for field in ("due_from", "due_to"):
            response = client.get("/tasks", params={field: "2026-07-16T12:00:00"})
            assert response.status_code == 400
            assert response.status_code < 500
            body = response.json()
            assert {
                "status", "code", "message", "component", "retryable",
                "trace_id", "details",
            } <= body.keys()
            assert body["status"] == "error"
            assert body["component"] == "user_tasks"
            assert body["retryable"] is False
            assert "timezone" not in response.text.lower()

        filtered = client.get("/tasks", params={
            "due_from": "2026-07-16T14:00:00+08:00",
            "due_to": "2026-07-16T16:00:00+08:00",
        })
        assert filtered.status_code == 200
        assert [task["id"] for task in filtered.json()] == [created.json()["id"]]


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


def test_user_task_api_corrupt_row_is_server_failure_without_leak(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        created = client.post("/tasks", json={"title": "corrupt me"})
        task_id = created.json()["id"]
        manager = client.app.state.system.database_manager
        with manager.lease("user_tasks") as conn:
            conn.execute(
                "UPDATE user_tasks SET metadata=? WHERE id=?",
                ('{"nested":{"token":"private-value"}} trailing', task_id),
            )
            conn.commit()
        response = client.get(f"/tasks/{task_id}")
        assert response.status_code >= 500
        assert response.status_code != 400
        assert response.json()["component"] == "user_tasks"
        assert "private-value" not in response.text
        assert "metadata" not in response.text.lower()


def test_user_task_api_full_workspace_headers_and_foreign_ids_are_isolated(
    tmp_path,
):
    app = create_app(make_test_settings(tmp_path))
    alpha = {
        "X-Tenant-ID": "tenant-a",
        "X-Workspace-ID": "alpha",
        "X-Namespace": "ops",
    }
    beta = {
        "X-Tenant-ID": "tenant-b",
        "X-Workspace-ID": "alpha",
        "X-Namespace": "ops",
    }
    with TestClient(app) as client:
        created = client.post(
            "/tasks",
            headers=alpha,
            json={
                "title": "Alpha only",
                "metadata": {
                    "business": "kept",
                    "workspace": {
                        "tenant_id": "attacker",
                        "workspace_id": "attacker",
                        "namespace": "attacker",
                    },
                },
            },
        )
        assert created.status_code == 201
        task = created.json()
        task_id = task["id"]
        assert task["metadata"] == {
            "business": "kept",
            "workspace": {
                "tenant_id": "tenant-a",
                "workspace_id": "alpha",
                "namespace": "ops",
            },
        }
        assert [item["id"] for item in client.get("/tasks", headers=alpha).json()] == [
            task_id
        ]
        assert client.get("/tasks", headers=beta).json() == []

        for method, path, payload in (
            ("get", f"/tasks/{task_id}", None),
            ("patch", f"/tasks/{task_id}", {"title": "leak"}),
            ("post", f"/tasks/{task_id}/complete", None),
            ("post", f"/tasks/{task_id}/cancel", None),
        ):
            kwargs = {"headers": beta}
            if payload is not None:
                kwargs["json"] = payload
            response = getattr(client, method)(path, **kwargs)
            assert response.status_code == 404
            assert "alpha only" not in response.text.casefold()
            assert "tenant-a" not in response.text
        unchanged = client.get(f"/tasks/{task_id}", headers=alpha).json()
        assert unchanged["title"] == "Alpha only"
        assert unchanged["status"] == "active"
        assert unchanged["revision"] == 1


def test_user_task_api_offset_and_terminal_range_contract(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        completed = []
        for title in ("First", "Second"):
            task_id = client.post("/tasks", json={"title": title}).json()["id"]
            completed.append(
                client.post(f"/tasks/{task_id}/complete").json()
            )
        page = client.get(
            "/tasks",
            params={"status": "completed", "limit": 1, "offset": 1},
        )
        assert page.status_code == 200
        assert len(page.json()) == 1
        assert page.json()[0]["id"] in {task["id"] for task in completed}

        instant = completed[0]["completed_at"]
        ranged = client.get(
            "/tasks",
            params={
                "completed_from": instant,
                "completed_to": "2100-01-01T00:00:00Z",
            },
        )
        assert ranged.status_code == 200
        assert completed[0]["id"] in {task["id"] for task in ranged.json()}

        invalid = client.get(
            "/tasks",
            params={
                "cancelled_from": "2026-07-27T08:00:00Z",
                "cancelled_to": "2026-07-27T08:00:00Z",
            },
        )
        assert invalid.status_code == 400
        assert invalid.json()["component"] == "user_tasks"


def test_user_task_api_overdue_uses_one_injected_request_instant(tmp_path):
    clock = MutableClock(datetime(2026, 7, 16, tzinfo=UTC))
    due_at = clock.now() + timedelta(days=1)
    app = create_app(make_test_settings(tmp_path), clock=clock)
    with TestClient(app) as client:
        future = client.post(
            "/tasks",
            json={
                "title": "Future against frozen clock",
                "due_at": due_at.isoformat(),
            },
        )
        assert future.status_code == 201
        assert future.json()["overdue"] is False

        boundary = client.post(
            "/tasks",
            json={
                "title": "Boundary against frozen clock",
                "due_at": clock.now().isoformat(),
            },
        )
        assert boundary.status_code == 201
        assert boundary.json()["overdue"] is False

        service = client.app.state.system.user_task_service
        original_current_instant = service.current_instant
        current_instant_calls = 0

        def counted_current_instant():
            nonlocal current_instant_calls
            current_instant_calls += 1
            return original_current_instant()

        service.current_instant = counted_current_instant
        not_overdue = client.get("/tasks", params={"overdue": "false"})
        assert not_overdue.status_code == 200
        assert current_instant_calls == 1
        assert {task["id"] for task in not_overdue.json()} == {
            future.json()["id"],
            boundary.json()["id"],
        }
        assert all(task["overdue"] is False for task in not_overdue.json())

        clock.advance(timedelta(days=2))
        current_instant_calls = 0
        overdue = client.get("/tasks", params={"overdue": "true"})
        assert overdue.status_code == 200
        assert current_instant_calls == 1
        assert future.json()["id"] in {task["id"] for task in overdue.json()}
        assert all(task["overdue"] is True for task in overdue.json())

    assert ".is_overdue()" not in inspect.getsource(task_routes)

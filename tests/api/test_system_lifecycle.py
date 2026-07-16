"""API lifecycle admission gate tests — exact contract assertions."""

from pathlib import Path
import tempfile
import asyncio
import ast
import inspect

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_runtime, get_system
from core.system.lifecycle import SystemLifecycleState
from core.system.settings import SystemSettings

TEST_TOKEN = "test-token-sp007"


def _app():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-api-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=True, api_token=TEST_TOKEN,
        enable_user_tasks=False, enable_reminders=False,
    )
    return create_app(settings)


@pytest.fixture
def client():
    with TestClient(_app()) as c:
        yield c

def _auth(): return {"Authorization": f"Bearer {TEST_TOKEN}"}

def _set(client, state):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client.app.state.system._lifecycle.transition(state))


class TestApiAdmissionExact:
    def test_draining_503_exact(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        resp = client.get("/tasks", headers=_auth())
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "system.draining"
        assert resp.headers.get("Retry-After") == "1"

    def test_stopped_503_exact(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        _set(client, SystemLifecycleState.STOPPED)
        resp = client.get("/tasks", headers=_auth())
        assert resp.status_code == 503
        assert resp.json()["code"] == "system.stopped"

    def test_failed_503_exact(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        _set(client, SystemLifecycleState.FAILED)
        resp = client.get("/tasks", headers=_auth())
        assert resp.status_code == 503
        assert resp.json()["code"] == "system.failed"

    def test_ready_invalid_token_401(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401


class TestHealthStableStates:
    def test_health_draining(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        resp = client.get("/health")
        assert resp.status_code == 200
        d = resp.json()
        assert d["lifecycle"] == "draining"
        assert d["accepting_work"] is False

    def test_health_stopped(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        _set(client, SystemLifecycleState.STOPPED)
        resp = client.get("/health")
        d = resp.json()
        assert d["lifecycle"] == "stopped"
        assert d["accepting_work"] is False

    def test_health_failed(self, client):
        _set(client, SystemLifecycleState.DRAINING)
        _set(client, SystemLifecycleState.FAILED)
        resp = client.get("/health")
        d = resp.json()
        assert d["lifecycle"] == "failed"
        assert d["accepting_work"] is False


def test_business_routes_do_not_import_unguarded_runtime_or_system_resolvers():
    routes_dir = Path(__file__).parents[2] / "api" / "routes"
    public_modules = {"health.py", "metrics.py"}
    forbidden = {"_get_system_unguarded", "_get_runtime_for_execute_only"}

    for route in routes_dir.glob("*.py"):
        if route.name in public_modules:
            continue
        tree = ast.parse(route.read_text(encoding="utf-8-sig"), filename=str(route))
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module == "api.dependencies"
            for alias in node.names
        }
        assert imported.isdisjoint(forbidden), route.name


def test_runtime_dependency_is_guarded_by_get_system():
    system_parameter = inspect.signature(get_runtime).parameters["system"]
    assert system_parameter.default.dependency is get_system

"""API lifecycle admission gate tests with real HTTP responses."""

from pathlib import Path
import tempfile
import asyncio

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
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

def _set_state(client, state):
    loop = asyncio.new_event_loop()
    loop.run_until_complete(client.app.state.system._lifecycle.transition(state))


class TestApiDraining:
    def test_draining_503_with_code_and_retry_after(self, client):
        _set_state(client, SystemLifecycleState.DRAINING)
        resp = client.get("/tasks", headers=_auth())
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "system.draining"
        assert resp.headers.get("Retry-After") == "1"

    def test_draining_health_accessible(self, client):
        _set_state(client, SystemLifecycleState.DRAINING)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lifecycle"] == "draining"
        assert data["accepting_work"] is False


class TestApiStopped:
    def test_stopped_503(self, client):
        _set_state(client, SystemLifecycleState.DRAINING)
        _set_state(client, SystemLifecycleState.STOPPED)
        resp = client.get("/tasks", headers=_auth())
        assert resp.status_code == 503
        assert resp.json()["code"] == "system.stopped"


class TestApiSecurity:
    def test_invalid_token_401_in_ready(self, client):
        resp = client.get("/tasks", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

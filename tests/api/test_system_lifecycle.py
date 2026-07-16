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

def _headers():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


class TestDrainingAdmission:
    def test_draining_returns_503_with_draining_code(self, client):
        system = client.app.state.system
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.DRAINING))
        resp = client.get("/tasks", headers=_headers())
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "system.draining"
        assert resp.headers.get("Retry-After") == "1"

    def test_draining_health_accessible(self, client):
        system = client.app.state.system
        loop = asyncio.new_event_loop()
        loop.run_until_complete(system._lifecycle.transition(SystemLifecycleState.DRAINING))
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["lifecycle"] == "draining"
        assert data["accepting_work"] is False


class TestReadyState:
    def test_ready_allows_authenticated_request(self, client):
        resp = client.get("/health", headers=_headers())
        assert resp.status_code == 200

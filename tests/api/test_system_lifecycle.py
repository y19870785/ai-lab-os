"""System lifecycle admission gate API tests."""

from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system.lifecycle import SystemLifecycleState
from core.system.settings import SystemSettings

TEST_TOKEN = "test-token-sp007"


def _app(lifecycle_state=None):
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp007-api-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=True, api_token=TEST_TOKEN,
        enable_user_tasks=False, enable_reminders=False,
    )
    return create_app(settings)


@pytest.fixture
def ready_client():
    with TestClient(_app()) as client:
        yield client


class TestAdmissionGate:
    def test_ready_accepts_authenticated_requests(self, ready_client):
        resp = ready_client.get("/health",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200

    def test_draining_rejects_business_requests_with_503(self, ready_client):
        system = ready_client.app.state.system
        if system is None:
            pytest.skip("system not started")
        # Force draining
        import asyncio
        async def drain():
            await system._lifecycle.transition(SystemLifecycleState.DRAINING)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(drain())
        resp = ready_client.get("/tasks",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 503

    def test_health_accessible_during_draining(self, ready_client):
        system = ready_client.app.state.system
        if system is None:
            pytest.skip("system not started")
        import asyncio
        async def drain():
            await system._lifecycle.transition(SystemLifecycleState.DRAINING)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(drain())
        resp = ready_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("lifecycle") == "draining"
        assert data.get("accepting_work") is False

    def test_draining_does_not_return_401(self, ready_client):
        system = ready_client.app.state.system
        if system is None:
            pytest.skip("system not started")
        import asyncio
        async def drain():
            await system._lifecycle.transition(SystemLifecycleState.DRAINING)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(drain())
        resp = ready_client.get("/tasks",
            headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 503
        assert resp.status_code != 401

    def test_invalid_token_still_401_in_ready(self, ready_client):
        resp = ready_client.get("/tasks",
            headers={"Authorization": "Bearer wrong-token"})
        assert resp.status_code == 401

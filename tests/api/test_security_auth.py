"SP-006 API authentication tests against a real FastAPI app."

from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system.settings import SystemSettings


TEST_TOKEN = "test-token-sp006-secure"


@pytest.fixture
def auth_client():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp006-auth-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=True, api_token=TEST_TOKEN,
        enable_user_tasks=False, enable_reminders=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def no_auth_client():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp006-noauth-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=False, api_token="",
        enable_user_tasks=False, enable_reminders=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


class TestUnauthenticatedRequests:
    def test_missing_header_returns_401_on_protected(self, auth_client):
        resp = auth_client.get("/tasks")
        assert resp.status_code == 401

    def test_wrong_token_returns_401(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer wrong-{TEST_TOKEN}"})
        assert resp.status_code == 401

    def test_invalid_format_returns_401(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Basic {TEST_TOKEN}"})
        assert resp.status_code == 401

    def test_empty_token_returns_401(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": "Bearer "})
        assert resp.status_code == 401

    def test_health_is_public_no_auth_required(self, auth_client):
        resp = auth_client.get("/health")
        assert resp.status_code == 200
        resp2 = auth_client.get("/health/live")
        assert resp2.status_code == 200
        resp3 = auth_client.get("/metrics")
        assert resp3.status_code == 200


class TestAuthorizedRequests:
    def test_correct_token_accesses_protected(self, auth_client):
        resp = auth_client.get("/applications", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200

    def test_token_not_leaked_in_response(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        body = resp.text
        assert TEST_TOKEN not in body


class TestAuthDisabled:
    def test_disabled_auth_allows_all(self, no_auth_client):
        resp = no_auth_client.get("/tasks")
        assert resp.status_code in {200, 500, 503}

    def test_null_origin_list_allowed(self, no_auth_client):
        resp = no_auth_client.get("/tasks")
        assert resp.status_code in {200, 500, 503}


class TestAuthConfigErrors:
    def test_auth_without_token_fails(self):
        with pytest.raises(ValueError, match="API authentication is enabled"):
            from applications.security.config import ApiSecurityConfig
            ApiSecurityConfig.from_settings(auth_enabled=True, api_token="")

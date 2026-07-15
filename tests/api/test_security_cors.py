"SP-006 CORS tests."

from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from core.system.settings import SystemSettings


@pytest.fixture
def cors_client():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp006-cors-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=False, api_token="",
        api_allowed_origins=["http://localhost:3000"],
        enable_user_tasks=False, enable_reminders=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def no_origin_client():
    data_dir = Path(tempfile.mkdtemp(prefix="ai-lab-sp006-noorigin-"))
    settings = SystemSettings(
        environment="test", provider_mode="test",
        data_dir=data_dir, sqlite_dir=data_dir / "sqlite",
        enable_api_auth=False, api_token="",
        api_allowed_origins=[],
        enable_user_tasks=False, enable_reminders=False,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        yield client


class TestCorsAllowlist:
    def test_no_allowed_origins_by_default(self, no_origin_client):
        resp = no_origin_client.get("/health", headers={"Origin": "http://example.com"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is None or acao == ""

    def test_whitelisted_origin_returns_cors_header(self, cors_client):
        resp = cors_client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_unlisted_origin_denied(self, cors_client):
        resp = cors_client.get("/health", headers={"Origin": "http://attacker.com"})
        acao = resp.headers.get("access-control-allow-origin")
        assert acao is None or acao == ""

    def test_preflight_options_works(self, cors_client):
        resp = cors_client.options(
            "/health",
            headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
        )
        assert resp.status_code in {200, 405}

    def test_cli_direct_call_works_without_origin(self, no_origin_client):
        resp = no_origin_client.get("/health")
        assert resp.status_code == 200


class TestCorsConfigErrors:
    def test_wildcard_rejected_with_auth(self):
        with pytest.raises(ValueError, match="Wildcard origin"):
            from applications.security.config import ApiSecurityConfig
            ApiSecurityConfig.from_settings(
                auth_enabled=True, api_token="test",
                allowed_origins=["*"],
            )

    def test_duplicate_origins_normalized(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(
            auth_enabled=False, api_token="",
            allowed_origins=["http://localhost:3000", "  http://localhost:3000  "],
        )
        assert len(cfg.allowed_origins) == 1
        assert cfg.allowed_origins[0] == "http://localhost:3000"

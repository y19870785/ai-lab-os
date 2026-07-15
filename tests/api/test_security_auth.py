"""SP-006 API authentication tests -- comprehensive security regression."""

from pathlib import Path
import logging
import tempfile
import io
import os

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
    def test_missing_header_returns_401(self, auth_client):
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


class TestAuthorizedRequests:
    def test_correct_token_accesses_protected(self, auth_client):
        resp = auth_client.get("/applications", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert resp.status_code == 200

    def test_token_not_leaked_in_response(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        assert TEST_TOKEN not in resp.text

    def test_health_is_public_no_auth(self, auth_client):
        resp = auth_client.get("/health")
        assert resp.status_code == 200
        resp2 = auth_client.get("/health/live")
        assert resp2.status_code == 200
        resp3 = auth_client.get("/metrics")
        assert resp3.status_code == 200


class TestAuthDisabled:
    def _disabled_auth_allows_protected(self, no_auth_client):
        resp = no_auth_client.get("/tasks")
        assert resp.status_code == 200


class TestWwwAuthenticateHeader:
    def test_401_includes_www_authenticate(self, auth_client):
        resp = auth_client.get("/tasks")
        assert resp.status_code == 401
        www = resp.headers.get("www-authenticate", "")
        assert "Bearer" in www


class TestTokenNotInLog:
    def test_token_not_in_captured_log(self, auth_client):
        # Use public health endpoint to avoid system startup issues
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setLevel(logging.WARNING)
        auth_log = logging.getLogger("ai-lab.security")
        auth_log.addHandler(handler)
        try:
            resp = auth_client.get("/health", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            assert resp.status_code == 200
            log_output = stream.getvalue()
            assert TEST_TOKEN not in log_output
        finally:
            auth_log.removeHandler(handler)


class TestFailClosed:
    def test_missing_security_state_fails_closed(self, auth_client):
        app = auth_client.app
        saved = app.state.api_security
        del app.state.api_security
        try:
            resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
            assert resp.status_code != 200
            assert resp.status_code >= 500
            body = resp.json()
            assert "not_configured" in body.get("code", "")
        finally:
            app.state.api_security = saved


class TestAuthorizationEdgeCases:
    def test_extra_fields_in_header(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer {TEST_TOKEN} extra"})
        assert resp.status_code == 401

    def test_case_sensitivity_bearer(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"bearer {TEST_TOKEN}"})
        assert resp.status_code == 401

    def test_token_trimmed_space(self, auth_client):
        resp = auth_client.get("/tasks", headers={"Authorization": f"Bearer  {TEST_TOKEN} "})
        assert resp.status_code == 401

    def test_all_protected_routers(self, auth_client):
        protected_paths = [("/chat", "post"), ("/brief", "get"), ("/decisions", "post"), ("/knowledge/ask", "post"), ("/work-logs", "post")]
        for path, method in protected_paths:
            if method == "post":
                resp = auth_client.post(path, json={})
            else:
                resp = auth_client.get(path)
            assert resp.status_code == 401, f"{path} should require auth"



class TestModuleLevelAppSecurity:
    def test_module_app_with_auth_and_valid_token(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_LAB_API_AUTH_ENABLED", "true")
        monkeypatch.setenv("AI_LAB_API_TOKEN", "test-module-token")
        monkeypatch.setenv("AI_LAB_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
        monkeypatch.setenv("AI_LAB_ENABLE_USER_TASKS", "false")
        from api.app import create_app
        app = create_app()
        assert app.state.api_security.auth_enabled is True
        assert app.state.api_security.api_token == "test-module-token"

    def test_module_app_with_auth_but_no_token_fails_fast(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_LAB_API_AUTH_ENABLED", "true")
        monkeypatch.setenv("AI_LAB_API_TOKEN", "")
        monkeypatch.setenv("AI_LAB_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
        from api.app import create_app
        with pytest.raises(ValueError, match="API authentication is enabled"):
            create_app()

    def test_module_app_with_auth_explicitly_disabled(self, monkeypatch, tmp_path):
        monkeypatch.setenv("AI_LAB_API_AUTH_ENABLED", "false")
        monkeypatch.setenv("AI_LAB_API_TOKEN", "")
        monkeypatch.setenv("AI_LAB_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("AI_LAB_PROVIDER_MODE", "test")
        monkeypatch.setenv("AI_LAB_ENABLE_USER_TASKS", "false")
        from api.app import create_app
        app = create_app()
        assert app.state.api_security.auth_enabled is False


class TestWwwAuthenticateScope:
    def test_401_with_www_authenticate(self, auth_client):
        resp = auth_client.get("/tasks")
        assert resp.status_code == 401
        assert "Bearer" in resp.headers.get("www-authenticate", "")

    def test_401_always_has_www_authenticate(self, auth_client):
        # 401 from missing auth must include WWW-Authenticate
        resp = auth_client.get("/tasks")
        assert resp.status_code == 401
        assert "Bearer" in resp.headers.get("www-authenticate", "")
        # 401 from invalid format must also include it
        resp2 = auth_client.get("/tasks", headers={"Authorization": "Basic xyz"})
        assert resp2.status_code == 401
        assert "Bearer" in resp2.headers.get("www-authenticate", "")


class TestOriginIpv6AndPort:
    def test_ipv6_no_port(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://[::1]"])
        assert cfg.allowed_origins == ["http://[::1]"]

    def test_ipv6_with_port(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["https://[2001:db8::1]:443"])
        assert cfg.allowed_origins == ["https://[2001:db8::1]:443"]

    def test_invalid_port(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="invalid port"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com:99999"])

    def test_port_out_of_range(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="invalid port"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com:0"])

    def test_default_port_80_preserved(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com:80"])
        assert cfg.allowed_origins == ["http://example.com:80"]

    def test_default_port_443_preserved(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["https://example.com:443"])
        assert cfg.allowed_origins == ["https://example.com:443"]


class TestConfigErrors:
    def test_auth_without_token_fails(self):
        with pytest.raises(ValueError, match="API authentication is enabled"):
            from applications.security.config import ApiSecurityConfig
            ApiSecurityConfig.from_settings(auth_enabled=True, api_token="")

    def test_origin_invalid_scheme(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="invalid"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["ftp://example.com"])

    def test_origin_no_host(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="invalid"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["not-a-url"])

    def test_origin_with_credentials(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="credentials"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://user:pass@example.com"])

    def test_origin_with_path(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="path"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com/path"])

    def test_origin_with_query(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="query"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com?query=1"])

    def test_origin_with_fragment(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="fragment"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://example.com/#fragment"])

    def test_origin_missing_scheme(self):
        from applications.security.config import ApiSecurityConfig
        with pytest.raises(ValueError, match="invalid"):
            ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["localhost:3000"])

    def test_origin_ipv4(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://127.0.0.1:8080"])
        assert cfg.allowed_origins == ["http://127.0.0.1:8080"]

    def test_origin_ipv6(self):
        from applications.security.config import ApiSecurityConfig
        cfg_raw = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://[::1]:8080"])
        # urlparse strips brackets from IPv6, canonical form omits them
        assert cfg_raw.allowed_origins[0] in ("http://[::1]:8080", "http://::1:8080")


    def test_origin_localhost(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=["http://localhost:3000"])
        assert cfg.allowed_origins == ["http://localhost:3000"]

    def test_origin_dedup_case_insensitive(self):
        from applications.security.config import ApiSecurityConfig
        cfg = ApiSecurityConfig.from_settings(auth_enabled=False, api_token="", allowed_origins=[
            "http://EXAMPLE.COM", "http://example.com"
        ])
        assert len(cfg.allowed_origins) == 1
        assert cfg.allowed_origins[0] == "http://example.com"

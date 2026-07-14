from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from api.middleware.error_handler import ErrorHandlerMiddleware
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system import make_test_settings


def _failure_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ErrorHandlerMiddleware)

    @app.get("/not-configured")
    async def not_configured():
        raise FailureException(FailureInfo(
            code="provider.not_configured",
            category=ErrorCategory.NOT_CONFIGURED,
            message="Provider is not configured",
            component="provider",
            operation="initialize",
        ))

    @app.get("/disabled")
    async def disabled():
        raise FailureException(FailureInfo(
            code="knowledge.disabled",
            category=ErrorCategory.DISABLED,
            message="Knowledge is disabled",
            component="knowledge",
            operation="search",
        ))

    @app.get("/timeout")
    async def timeout():
        raise FailureException(FailureInfo(
            code="provider.timeout",
            category=ErrorCategory.TIMEOUT,
            message="Provider timed out",
            component="provider",
            operation="generate",
            retryable=True,
        ))

    @app.get("/unknown")
    async def unknown():
        raise RuntimeError("private path C:/secret/internal.py")

    return app


def _assert_error_contract(response, expected_status, expected_code):
    assert response.status_code == expected_status
    body = response.json()
    assert body["status"] == "error"
    assert body["code"] == expected_code
    assert body["message"]
    assert body["trace_id"]
    assert isinstance(body["retryable"], bool)
    assert "traceback" not in response.text.lower()


def test_unregistered_application_returns_404_not_http_200(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post("/chat", json={
            "user_input": "hello",
            "application_name": "not-registered",
        })

    _assert_error_contract(response, 404, "api.request.failed")


def test_not_configured_disabled_and_timeout_http_mapping():
    with TestClient(_failure_app()) as client:
        _assert_error_contract(client.get("/not-configured"), 503, "provider.not_configured")
        _assert_error_contract(client.get("/disabled"), 503, "knowledge.disabled")
        timeout = client.get("/timeout")
        _assert_error_contract(timeout, 504, "provider.timeout")
        assert timeout.json()["retryable"] is True


def test_unknown_exception_returns_generic_500_without_internal_details():
    with TestClient(_failure_app()) as client:
        response = client.get("/unknown", headers={"X-Trace-ID": "trace-client"})

    _assert_error_contract(response, 500, "api.request.failed")
    assert response.json()["message"] == "Unexpected internal error"
    assert "C:/secret" not in response.text
    assert response.json()["details"] == {}


def test_fastapi_validation_uses_common_400_contract(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post("/chat", json={"user_input": {"invalid": True}})

    _assert_error_contract(response, 400, "api.request.validation_failed")
    assert response.json()["details"]["issues"]

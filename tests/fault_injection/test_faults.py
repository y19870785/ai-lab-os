"""Fault injection tests for explicit application dispatch."""

import asyncio

import pytest

from applications.config import ApplicationConfig
from applications.exceptions import ApplicationNotRegisteredError
from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationRequest, ApplicationResponse,
)
from applications.runtime import ApplicationRuntime

pytestmark = pytest.mark.asyncio(loop_scope="function")


class EchoApplication:
    async def run(self, request):
        return ApplicationResponse(answer=request.user_input, mode="mock")


class FailingApplication:
    async def run(self, request):
        raise RuntimeError("agent execution failed")


async def make_runtime(instance=None, name="test"):
    runtime = ApplicationRuntime(config=ApplicationConfig(provider_mode="mock"))
    await runtime.initialize()
    info = ApplicationInfo(name=name)
    await runtime.register_application(
        info,
        ApplicationManifest(name=name, entrypoint="test"),
        instance or EchoApplication(),
    )
    return runtime


class TestFaultInjection:
    async def test_missing_api_key_uses_explicit_test_app(self):
        runtime = await make_runtime()
        response = await runtime.execute(ApplicationRequest(
            application_name="test", user_input="Hello"
        ))
        assert response.status == "ok"
        assert response.mode == "mock"
        await runtime.shutdown()

    async def test_application_failure_is_not_converted_to_success(self):
        runtime = await make_runtime(FailingApplication())
        with pytest.raises(RuntimeError, match="agent execution failed"):
            await runtime.execute(ApplicationRequest(application_name="test", user_input="First"))
        await runtime.shutdown()

    async def test_invalid_app_name_is_rejected(self):
        runtime = ApplicationRuntime()
        await runtime.initialize()
        for name in ["", "   ", "!@#$"]:
            with pytest.raises(ApplicationNotRegisteredError):
                await runtime.execute(ApplicationRequest(application_name=name, user_input="Test"))
        await runtime.shutdown()

    async def test_error_message_sanitized(self):
        from core.security import sanitize_error_message

        msg = "Error in C:\\Users\\hechao\\secret line 42 with key " + "sk-" + "abc123def456"
        clean = sanitize_error_message(msg)
        assert "C:\\" not in clean

    async def test_empty_user_input_reaches_registered_app(self):
        runtime = await make_runtime()
        response = await runtime.execute(ApplicationRequest(application_name="test", user_input=""))
        assert response.status == "ok"
        await runtime.shutdown()

    async def test_trace_id_present(self):
        runtime = await make_runtime()
        response = await runtime.execute(ApplicationRequest(application_name="test", user_input="Test"))
        assert response.trace_id != ""
        await runtime.shutdown()

    async def test_concurrent_requests_use_one_registered_instance(self):
        runtime = await make_runtime()

        async def execute(index):
            return await runtime.execute(ApplicationRequest(
                application_name="test", user_input=f"Concurrent {index}"
            ))

        results = await asyncio.gather(*(execute(i) for i in range(10)))
        assert all(result.status == "ok" for result in results)
        await runtime.shutdown()

"""Fault Injection Tests。"""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")


class TestFaultInjection:

    async def test_missing_api_key_no_crash(self):
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        import os
        old_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            req = ApplicationRequest(application_name="test", user_input="Hello")
            resp = await rt.execute(req)
            assert resp.status == "ok"
            assert resp.mode == "mock"
        finally:
            if old_key:
                os.environ["OPENAI_API_KEY"] = old_key
        await rt.shutdown()

    async def test_agent_execution_failure_no_crash(self):
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        resp1 = await rt.execute(ApplicationRequest(user_input="First"))
        assert resp1.status == "ok"
        resp2 = await rt.execute(ApplicationRequest(user_input="Second"))
        assert resp2.status == "ok"
        await rt.shutdown()

    async def test_invalid_app_name_no_crash(self):
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        for name in ["", "   ", "!@#$"]:
            resp = await rt.execute(ApplicationRequest(application_name=name, user_input="Test"))
            assert resp.status == "ok"
        await rt.shutdown()

    async def test_error_message_sanitized(self):
        from core.security import sanitize_error_message
        msg = "Error in C:\\Users\\hechao\\secret line 42 with key sk-abc123def456"
        clean = sanitize_error_message(msg)
        assert "C:\\" not in clean

    async def test_empty_user_input_no_crash(self):
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        resp = await rt.execute(ApplicationRequest(user_input=""))
        assert resp.status == "ok"
        await rt.shutdown()

    async def test_trace_id_present(self):
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        resp = await rt.execute(ApplicationRequest(user_input="Test"))
        assert resp.trace_id != ""
        await rt.shutdown()

    async def test_concurrent_requests_no_crash(self):
        import asyncio
        from applications.runtime import ApplicationRuntime
        from applications.models import ApplicationRequest
        rt = ApplicationRuntime()
        await rt.initialize()
        async def make_request(i):
            return await rt.execute(ApplicationRequest(user_input=f"Concurrent {i}"))
        results = await asyncio.gather(*[make_request(i) for i in range(10)])
        assert all(r.status == "ok" for r in results)
        await rt.shutdown()

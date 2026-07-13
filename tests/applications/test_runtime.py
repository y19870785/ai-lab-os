"""Application Runtime Tests。"""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from applications.runtime import ApplicationRuntime
from applications.registry import ApplicationRegistry
from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationRequest,
)


class TestApplicationRuntime:

    async def test_initialize_and_shutdown(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        hc = await rt.health_check()
        assert hc["status"] == "healthy"
        await rt.shutdown()

    async def test_register_application(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        info = ApplicationInfo(name="test-app")
        manifest = ApplicationManifest(name="test-app", version="1.0", entrypoint="main")
        await rt.register_application(info, manifest)
        apps = await rt.list_applications()
        assert len(apps) == 1
        await rt.shutdown()

    async def test_execute_no_deps(self):
        """执行请求——无 Orchestrator/Agent 时使用 echo fallback。"""
        rt = ApplicationRuntime()
        await rt.initialize()
        req = ApplicationRequest(application_name="test", user_input="Hello world")
        resp = await rt.execute(req)
        assert resp.status == "ok"
        assert "Hello world" in resp.answer
        assert resp.mode == "mock"
        assert resp.trace_id != ""
        await rt.shutdown()

    async def test_execute_auto_creates_app(self):
        """未注册应用时自动创建。"""
        rt = ApplicationRuntime()
        await rt.initialize()
        req = ApplicationRequest(application_name="unknown-app", user_input="Test")
        resp = await rt.execute(req)
        assert resp.status == "ok"
        apps = await rt.list_applications()
        assert len(apps) == 1
        assert apps[0].name == "unknown-app"
        await rt.shutdown()

    async def test_list_applications(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        apps = await rt.list_applications()
        assert isinstance(apps, list)
        await rt.shutdown()

    async def test_app_count(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        assert rt.app_count == 0
        info = ApplicationInfo(name="a1")
        await rt.register_application(info, ApplicationManifest(name="a1", version="1.0", entrypoint="main"))
        assert rt.app_count == 1
        await rt.shutdown()

    async def test_provider_mode_detection(self):
        rt = ApplicationRuntime()
        mode = rt._detect_provider_mode()
        assert mode in ("mock", "real")

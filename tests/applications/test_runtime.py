"""Application Runtime Tests。"""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from applications.runtime import ApplicationRuntime
from applications.registry import ApplicationRegistry
from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationRequest, ApplicationResponse,
)
from applications.exceptions import ApplicationAlreadyRegisteredError, ApplicationNotRegisteredError
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION


class _TestApplication:
    async def run(self, request):
        return ApplicationResponse(answer=request.user_input, mode="mock")


class TestApplicationRuntime:

    async def test_initialize_and_shutdown(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        hc = await rt.health_check()
        assert hc["status"] == "healthy"
        await rt.shutdown()

    async def test_register_application(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        info = ApplicationInfo(name="test-app")
        manifest = ApplicationManifest(name="test-app", version="1.0", entrypoint="main")
        await rt.register_application(info, manifest)
        apps = await rt.list_applications()
        assert len(apps) == 1
        await rt.shutdown()

    async def test_execute_registered_instance(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        info = ApplicationInfo(name="test")
        await rt.register_application(
            info, ApplicationManifest(name="test", entrypoint="test"), _TestApplication()
        )
        req = ApplicationRequest(application_name="test", user_input="Hello world")
        resp = await rt.execute(req)
        assert resp.status == "ok"
        assert "Hello world" in resp.answer
        assert resp.mode == "mock"
        assert resp.trace_id != ""
        await rt.shutdown()

    async def test_execute_rejects_unregistered_app(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        req = ApplicationRequest(application_name="unknown-app", user_input="Test")
        with pytest.raises(ApplicationNotRegisteredError):
            await rt.execute(req)
        assert await rt.list_applications() == []
        await rt.shutdown()

    async def test_list_applications(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        apps = await rt.list_applications()
        assert isinstance(apps, list)
        await rt.shutdown()

    async def test_duplicate_name_is_rejected(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        info = ApplicationInfo(name="same-name")
        manifest = ApplicationManifest(name="same-name", entrypoint="test")
        await rt.register_application(info, manifest, _TestApplication())
        with pytest.raises(ApplicationAlreadyRegisteredError):
            await rt.register_application(
                ApplicationInfo(name="same-name"), manifest, _TestApplication()
            )

    async def test_app_count(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        await rt.initialize()
        assert rt.app_count == 0
        info = ApplicationInfo(name="a1")
        await rt.register_application(info, ApplicationManifest(name="a1", version="1.0", entrypoint="main"))
        assert rt.app_count == 1
        await rt.shutdown()

    async def test_provider_mode_detection(self):
        rt = ApplicationRuntime(admission=PERMISSIVE_TEST_ADMISSION)
        mode = rt._detect_provider_mode()
        assert mode == "invalid"

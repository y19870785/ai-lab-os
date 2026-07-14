"""Alpha Application Integration Test。"""
import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from applications.runtime import ApplicationRuntime
from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationRequest, ApplicationResponse,
)
from applications.alpha_assistant.application import AlphaAssistant


class _ExplicitMockRuntime:
    async def execute(self, request):
        return ApplicationResponse(answer=f"[mock] {request.user_input}", mode="mock")

class TestAlphaIntegration:

    async def test_alpha_app_registration(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        info = ApplicationInfo(name="alpha_assistant", version="1.0.0")
        manifest = ApplicationManifest(
            name="alpha_assistant", version="1.0", entrypoint="applications.alpha_assistant.application:AlphaAssistant",
            required_agents=["default-agent"], required_tools=["echo"],
        )
        await rt.register_application(info, manifest)
        apps = await rt.list_applications()
        assert any(a.name == "alpha_assistant" for a in apps)
        await rt.shutdown()

    async def test_alpha_execution_mock(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        info = ApplicationInfo(name="alpha_assistant")
        manifest = ApplicationManifest(name="alpha_assistant", entrypoint="alpha")
        await rt.register_application(info, manifest, AlphaAssistant(_ExplicitMockRuntime()))
        req = ApplicationRequest(application_name="alpha_assistant", user_input="What is AI-Lab?")
        resp = await rt.execute(req)
        assert resp.status == "ok"
        assert resp.mode == "mock"  # No API key
        assert "[mock]" in resp.answer
        await rt.shutdown()

    async def test_alpha_multiple_requests(self):
        rt = ApplicationRuntime()
        await rt.initialize()
        info = ApplicationInfo(name="alpha_assistant")
        manifest = ApplicationManifest(name="alpha_assistant", entrypoint="alpha")
        await rt.register_application(info, manifest, AlphaAssistant(_ExplicitMockRuntime()))
        for i in range(5):
            req = ApplicationRequest(application_name="alpha_assistant", user_input=f"Question {i}")
            resp = await rt.execute(req)
            assert resp.status == "ok"
        await rt.shutdown()

    async def test_manifest_file_loads(self):
        from applications.manifest import load_manifest
        import os
        manifest_path = os.path.join(os.path.dirname(__file__), "..", "..", "applications", "alpha_assistant", "manifest.yaml")
        if os.path.exists(manifest_path):
            m = load_manifest(manifest_path)
            assert m.name == "alpha_assistant"
            assert m.version == "1.0.0"

    async def test_deploy_configs_exist(self):
        import os
        base = os.path.dirname(__file__) + "/../.."
        assert os.path.exists(os.path.join(base, "deploy/Dockerfile"))
        assert os.path.exists(os.path.join(base, "deploy/docker-compose.yml"))

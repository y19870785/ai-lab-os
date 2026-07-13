"""Application Models + Manifest Tests。"""
import pytest
from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationContext,
    ApplicationRequest, ApplicationResponse, ApplicationStatus,
)
from applications.manifest import load_manifest, validate_manifest
from applications.registry import ApplicationRegistry
from applications.exceptions import ApplicationNotFoundError

class TestApplicationModels:
    def test_application_info(self):
        info = ApplicationInfo(name="test-app", version="1.0.0")
        assert info.application_id != ""

    def test_manifest(self):
        m = ApplicationManifest(name="app", version="1.0", entrypoint="main",
                                required_agents=["agent-1"], required_tools=["echo"])
        assert len(m.required_agents) == 1

    def test_application_context(self):
        ctx = ApplicationContext(application_id="a1", environment="dev")
        assert ctx.application_id == "a1"
        assert ctx.environment == "dev"

    def test_application_request(self):
        req = ApplicationRequest(application_name="alpha", user_input="Hello")
        assert req.mode == "sync"

    def test_application_response(self):
        resp = ApplicationResponse(answer="Hi", status="ok", mode="mock")
        assert resp.mode == "mock"

    def test_manifest_validation(self):
        m = ApplicationManifest(name="", version="", entrypoint="")
        errors = validate_manifest(m)
        assert len(errors) == 3

class TestApplicationRegistry:
    def test_register_and_find(self):
        reg = ApplicationRegistry()
        info = ApplicationInfo(name="alpha")
        manifest = ApplicationManifest(name="alpha", version="1.0", entrypoint="main")
        reg.register(info, manifest)
        assert reg.count == 1
        found = reg.find_by_name("alpha")
        assert len(found) == 1

    def test_get_nonexistent_raises(self):
        reg = ApplicationRegistry()
        with pytest.raises(ApplicationNotFoundError):
            reg.get("nonexistent")

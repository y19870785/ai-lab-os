"""Interactive CLI must reuse the shared Composition Root."""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from core.errors import FailureException
from core.system import make_test_settings
from core.system.admission import WorkAdmissionGate
from core.system.lifecycle import LifecycleStateMachine, SystemLifecycleState


@pytest.mark.asyncio(loop_scope="function")
async def test_interactive_cli_uses_and_closes_system(monkeypatch, tmp_path):
    from cli import ceo

    calls = {"create": 0, "start": 0, "shutdown": 0}

    class FakeSystem:
        application_runtime = SimpleNamespace()

        async def start(self):
            calls["start"] += 1

        async def shutdown(self):
            calls["shutdown"] += 1

    async def fake_create(settings):
        calls["create"] += 1
        return FakeSystem()

    monkeypatch.setattr(ceo, "load_system_settings", lambda: make_test_settings(tmp_path))
    monkeypatch.setattr(ceo, "create_system", fake_create)
    monkeypatch.setattr(ceo, "get_provider_info", lambda: {
        "mode": "test", "provider": "Mock", "base_url": "N/A",
        "model": "mock-v1", "api_key_masked": "",
    })
    monkeypatch.setattr("builtins.input", lambda _: "/exit")

    await ceo.run_ceo()
    assert calls == {"create": 1, "start": 1, "shutdown": 1}


@pytest.mark.asyncio(loop_scope="function")
async def test_one_shot_cli_inherits_application_runtime_admission(monkeypatch, tmp_path):
    from cli import runtime as cli_runtime

    lifecycle = LifecycleStateMachine()
    await lifecycle.transition(SystemLifecycleState.STARTING)
    await lifecycle.transition(SystemLifecycleState.READY)
    await lifecycle.transition(SystemLifecycleState.DRAINING)
    admission = WorkAdmissionGate(lifecycle)
    calls = {"execute": 0, "shutdown": 0}

    class GatedRuntime:
        async def execute(self, request):
            with admission.admit():
                calls["execute"] += 1
                return SimpleNamespace(status="ok")

    class FakeSystem:
        application_runtime = GatedRuntime()

        async def start(self):
            return None

        async def shutdown(self):
            calls["shutdown"] += 1

    async def fake_create(settings):
        return FakeSystem()

    monkeypatch.setattr(
        cli_runtime,
        "load_system_settings",
        lambda: make_test_settings(tmp_path),
    )
    monkeypatch.setattr(cli_runtime, "create_system", fake_create)

    with pytest.raises(FailureException) as exc_info:
        await cli_runtime.execute_ceo_request("status")

    assert exc_info.value.failure.code == "system.draining"
    assert calls == {"execute": 0, "shutdown": 1}


@pytest.mark.asyncio(loop_scope="function")
async def test_one_shot_ceo_uses_profile_workspace_and_fresh_trace(
    monkeypatch, tmp_path
):
    from cli import runtime as cli_runtime

    settings = replace(
        make_test_settings(tmp_path),
        workspace_tenant_id="tenant",
        workspace_id="workspace",
        workspace_namespace="operations",
        workspace_session_id="session",
        workspace_agent_id="agent",
    )
    requests = []

    class CapturingRuntime:
        async def execute(self, request):
            requests.append(request)
            return SimpleNamespace(status="ok")

    class FakeSystem:
        application_runtime = CapturingRuntime()

        async def start(self):
            return None

        async def shutdown(self):
            return None

    async def fake_create(_settings):
        return FakeSystem()

    monkeypatch.setattr(cli_runtime, "load_system_settings", lambda: settings)
    monkeypatch.setattr(cli_runtime, "create_system", fake_create)

    await cli_runtime.execute_ceo_request("简报")
    await cli_runtime.execute_ceo_request("任务")

    assert [request.workspace_key.model_dump(exclude={"trace_id"}) for request in requests] == [
        {
            "tenant_id": "tenant",
            "workspace_id": "workspace",
            "namespace": "operations",
            "user_id": "",
            "session_id": "session",
            "agent_id": "agent",
        },
        {
            "tenant_id": "tenant",
            "workspace_id": "workspace",
            "namespace": "operations",
            "user_id": "",
            "session_id": "session",
            "agent_id": "agent",
        },
    ]
    assert requests[0].workspace_key.trace_id != requests[1].workspace_key.trace_id

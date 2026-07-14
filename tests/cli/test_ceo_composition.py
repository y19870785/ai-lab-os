"""Interactive CLI must reuse the shared Composition Root."""

from types import SimpleNamespace

import pytest

from core.system import make_test_settings


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

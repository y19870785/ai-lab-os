"""Tests for ProviderRegistry."""
import pytest
from core.providers import (
    ProviderRegistry, ProviderType, ProviderStatus, ProviderInfo, ProviderCapability,
    ProviderNotFoundError,
)


# Minimal concrete provider for testing
from core.providers.base import BaseProvider


class _TestProvider(BaseProvider):
    def __init__(self, pid: str = "test-001"):
        info = ProviderInfo(
            provider_id=pid,
            provider_type=ProviderType.LLM,
            name="test",
            capabilities=[ProviderCapability(name="generate")],
        )
        super().__init__(info)
        self.init_called = False
        self.shutdown_called = False

    async def _do_initialize(self) -> None:
        self.init_called = True

    async def _do_shutdown(self) -> None:
        self.shutdown_called = True

    async def _do_health_check(self) -> bool:
        return True


class TestProviderRegistry:
    def test_register_and_get(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        assert reg.exists(ProviderType.LLM, "test")
        assert reg.provider_count == 1

        provider = reg.get(ProviderType.LLM, "test")
        assert isinstance(provider, _TestProvider)
        assert provider.metadata().status == ProviderStatus.UNINITIALIZED

    def test_get_default(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        provider = reg.get(ProviderType.LLM)  # no name = default
        assert isinstance(provider, _TestProvider)

    def test_get_nonexistent_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            reg.get(ProviderType.LLM, "nonexistent")

    def test_get_no_default_raises(self):
        reg = ProviderRegistry()
        with pytest.raises(ProviderNotFoundError):
            reg.get(ProviderType.LLM)

    def test_list(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        reg.register(ProviderType.EMBEDDING, "emb-test", _TestProvider)
        assert "test" in reg.list(ProviderType.LLM)
        assert "emb-test" in reg.list(ProviderType.EMBEDDING)
        assert len(reg.list()) == 2

    def test_unregister(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        assert reg.unregister(ProviderType.LLM, "test")
        assert not reg.exists(ProviderType.LLM, "test")

    def test_cache_instance(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        p1 = reg.get(ProviderType.LLM, "test")
        p2 = reg.get(ProviderType.LLM, "test")
        assert p1 is p2  # Same instance

    def test_find_by_capability(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        results = reg.find_by_capability("generate")
        assert len(results) == 1
        assert results[0] == (ProviderType.LLM, "test")

    def test_instance_count(self):
        reg = ProviderRegistry()
        reg.register(ProviderType.LLM, "test", _TestProvider)
        assert reg.instance_count == 0
        reg.get(ProviderType.LLM, "test")
        assert reg.instance_count == 1

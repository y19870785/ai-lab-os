"""Tests for provider data models."""
import pytest
from core.providers.models import (
    ProviderType, ProviderStatus, ProviderCapability,
    ProviderInfo, ProviderConfig,
)


class TestProviderModels:
    def test_provider_type_values(self):
        assert ProviderType.LLM.value == "llm"
        assert ProviderType.EMBEDDING.value == "embedding"
        assert ProviderType.VECTOR.value == "vector"
        assert ProviderType.STORAGE.value == "storage"

    def test_provider_status_values(self):
        assert ProviderStatus.UNINITIALIZED.value == "uninitialized"
        assert ProviderStatus.READY.value == "ready"
        assert ProviderStatus.SHUTDOWN.value == "shutdown"

    def test_provider_info_creation(self):
        info = ProviderInfo(
            provider_id="test-001",
            provider_type=ProviderType.LLM,
            name="test-provider",
            version="1.0.0",
            description="Test provider",
            capabilities=[ProviderCapability(name="generate", version="1.0")],
        )
        assert info.provider_id == "test-001"
        assert info.provider_type == ProviderType.LLM
        assert info.status == ProviderStatus.UNINITIALIZED
        assert len(info.capabilities) == 1
        assert info.capabilities[0].name == "generate"

    def test_provider_config_creation(self):
        config = ProviderConfig(
            provider_type=ProviderType.LLM,
            provider_name="mock",
            settings={"temperature": 0.7},
        )
        assert config.provider_type == ProviderType.LLM
        assert config.provider_name == "mock"
        assert config.enabled is True
        assert config.priority == 0

    def test_provider_capability_defaults(self):
        cap = ProviderCapability(name="search")
        assert cap.name == "search"
        assert cap.version == "1.0.0"
        assert cap.description == ""
        assert cap.parameters == {}

"""Tests for ProviderFactory."""
import pytest
from core.providers import (
    ProviderFactory, ProviderRegistry, ProviderType, ProviderStatus,
    ProviderConfig,
)


class TestProviderFactory:
    def test_register_builtins(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        # 7 providers: mock(4) + openai(llm+embedding) + chroma(vector)
        assert reg.provider_count == 7
        assert reg.exists(ProviderType.LLM, "mock")
        assert reg.exists(ProviderType.LLM, "openai")
        assert reg.exists(ProviderType.EMBEDDING, "mock")
        assert reg.exists(ProviderType.EMBEDDING, "openai")
        assert reg.exists(ProviderType.VECTOR, "mock")
        assert reg.exists(ProviderType.VECTOR, "chroma")
        assert reg.exists(ProviderType.STORAGE, "mock")

    @pytest.mark.asyncio
    async def test_initialize_all(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        providers = await factory.initialize_all()
        # At least 4 mock providers initialize; real ones may fail
        assert len(providers) >= 4
        for p in providers:
            assert p.metadata().status == ProviderStatus.READY

    @pytest.mark.asyncio
    async def test_get_llm_mock(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        await factory.initialize_all()
        llm = factory.get_llm("mock")
        assert llm.is_available()

    @pytest.mark.asyncio
    async def test_get_embedding_mock(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        await factory.initialize_all()
        emb = factory.get_embedding("mock")
        assert emb.is_available()

    @pytest.mark.asyncio
    async def test_get_vector_mock(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        await factory.initialize_all()
        vec = factory.get_vector("mock")
        assert vec.is_available()

    @pytest.mark.asyncio
    async def test_get_storage_mock(self):
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        await factory.initialize_all()
        sto = factory.get_storage("mock")
        assert sto.is_available()

    @pytest.mark.asyncio
    async def test_real_providers_registered(self):
        """Verify real providers are registered but gracefully degrade."""
        reg = ProviderRegistry()
        factory = ProviderFactory(reg)
        factory.register_builtins()
        # OpenAI LLM is registered
        llm = factory.get_llm("openai")
        assert llm is not None
        # But may not be available without API key
        # (just checking registration works, not initialization)

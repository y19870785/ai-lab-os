"""Tests for Mock Providers — LLM, Embedding, Vector, Storage."""
import pytest
from core.providers.llm import MockLLMProvider, LLMRequest, Message
from core.providers.embedding import MockEmbeddingProvider
from core.providers.vector import MockVectorProvider, VectorRecord, VectorSearchQuery
from core.providers.storage import MockStorageProvider
from core.providers.models import ProviderStatus


class TestMockLLM:
    @pytest.mark.asyncio
    async def test_initialize_and_ready(self):
        llm = MockLLMProvider()
        assert not llm.is_available()
        await llm.initialize()
        assert llm.is_available()
        assert llm.metadata().status == ProviderStatus.READY

    @pytest.mark.asyncio
    async def test_generate(self):
        llm = MockLLMProvider()
        await llm.initialize()
        req = LLMRequest(messages=[Message(role="user", content="hello")])
        resp = await llm.generate(req)
        assert "[mock] hello" in resp.content
        assert resp.finish_reason == "stop"
        assert resp.usage["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_stream(self):
        llm = MockLLMProvider()
        await llm.initialize()
        req = LLMRequest(messages=[Message(role="user", content="hello world")])
        chunks = [c async for c in llm.stream(req)]
        assert len(chunks) > 0
        assert any("mock" in c for c in chunks)

    @pytest.mark.asyncio
    async def test_count_tokens(self):
        llm = MockLLMProvider()
        await llm.initialize()
        tc = await llm.count_tokens([Message(role="user", content="hello world")])
        assert tc.total_tokens == 2

    @pytest.mark.asyncio
    async def test_list_models(self):
        llm = MockLLMProvider()
        await llm.initialize()
        models = await llm.list_models()
        assert "mock-v1" in models

    def test_capabilities(self):
        llm = MockLLMProvider()
        assert llm.supports_function_call()
        assert not llm.supports_vision()
        assert not llm.supports_reasoning()
        assert llm.supports_json_mode()

    @pytest.mark.asyncio
    async def test_shutdown(self):
        llm = MockLLMProvider()
        await llm.initialize()
        assert llm.is_available()
        await llm.shutdown()
        assert not llm.is_available()
        assert llm.metadata().status == ProviderStatus.SHUTDOWN


class TestMockEmbedding:
    @pytest.mark.asyncio
    async def test_embed(self):
        emb = MockEmbeddingProvider()
        await emb.initialize()
        vectors = await emb.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == emb.dimension()
        assert vectors[0] != vectors[1]  # Different texts

    @pytest.mark.asyncio
    async def test_embed_query(self):
        emb = MockEmbeddingProvider()
        await emb.initialize()
        v1 = await emb.embed_query("hello")
        v2 = await emb.embed_query("hello")
        assert v1 == v2  # Deterministic

    def test_dimension(self):
        emb = MockEmbeddingProvider()
        assert emb.dimension() == 384

    def test_normalize(self):
        emb = MockEmbeddingProvider()
        v = [3.0, 4.0]  # magnitude 5
        n = emb.normalize(v)
        assert abs((n[0]**2 + n[1]**2) - 1.0) < 0.001


class TestMockVector:
    @pytest.mark.asyncio
    async def test_insert_and_search(self):
        vec = MockVectorProvider()
        await vec.initialize()
        await vec.insert("test", [VectorRecord(id="a", vector=[1.0, 0.0])])
        await vec.insert("test", [VectorRecord(id="b", vector=[0.0, 1.0])])

        from core.providers.vector import VectorSearchQuery
        results = await vec.search("test", VectorSearchQuery(vector=[1.0, 0.0], top_k=2))
        assert len(results) == 2
        assert results[0].id == "a"  # closer match

    @pytest.mark.asyncio
    async def test_delete(self):
        vec = MockVectorProvider()
        await vec.initialize()
        await vec.insert("test", [VectorRecord(id="x", vector=[1.0])])
        assert await vec.delete("test", ["x"]) == 1
        results = await vec.search("test", VectorSearchQuery(vector=[1.0]))
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_collection_info(self):
        vec = MockVectorProvider()
        await vec.initialize()
        await vec.insert("test", [VectorRecord(id="a", vector=[1.0, 2.0, 3.0])])
        info = await vec.collection_info("test")
        assert info["count"] == 1
        assert info["dimension"] == 3

    @pytest.mark.asyncio
    async def test_list_and_delete_collections(self):
        vec = MockVectorProvider()
        await vec.initialize()
        await vec.insert("c1", [VectorRecord(id="a", vector=[1.0])])
        await vec.insert("c2", [VectorRecord(id="b", vector=[2.0])])
        cols = await vec.list_collections()
        assert set(cols) == {"c1", "c2"}
        assert await vec.delete_collection("c1")
        assert await vec.list_collections() == ["c2"]


class TestMockStorage:
    @pytest.mark.asyncio
    async def test_save_and_load(self):
        sto = MockStorageProvider()
        await sto.initialize()
        await sto.save("key1", b"hello world")
        data = await sto.load("key1")
        assert data == b"hello world"

    @pytest.mark.asyncio
    async def test_load_missing(self):
        sto = MockStorageProvider()
        await sto.initialize()
        assert await sto.load("nope") is None

    @pytest.mark.asyncio
    async def test_exists(self):
        sto = MockStorageProvider()
        await sto.initialize()
        assert not await sto.exists("key1")
        await sto.save("key1", b"data")
        assert await sto.exists("key1")

    @pytest.mark.asyncio
    async def test_delete(self):
        sto = MockStorageProvider()
        await sto.initialize()
        await sto.save("key1", b"data")
        assert await sto.delete("key1")
        assert not await sto.exists("key1")
        assert not await sto.delete("key1")  # Already gone

    @pytest.mark.asyncio
    async def test_list_keys(self):
        sto = MockStorageProvider()
        await sto.initialize()
        await sto.save("prefix/a", b"a")
        await sto.save("prefix/b", b"b")
        await sto.save("other/c", b"c")
        keys = await sto.list_keys("prefix/")
        assert set(keys) == {"prefix/a", "prefix/b"}

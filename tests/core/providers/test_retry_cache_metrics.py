"""Tests for RetryPolicy, ProviderCache, MetricsCollector."""
import pytest
from core.providers.retry import RetryPolicy, RetryConfig, RetryResult
from core.providers.cache import ProviderCache, CacheConfig
from core.providers.metrics import MetricsCollector


class TestRetryPolicy:
    @pytest.mark.asyncio
    async def test_success_first_try(self):
        policy = RetryPolicy(RetryConfig(max_retries=3, base_delay_seconds=0.01))
        async def ok_fn(): return "ok"
        result = await policy.execute(ok_fn)
        assert result.success
        assert result.result == "ok"
        assert result.attempts == 1

    @pytest.mark.asyncio
    async def test_retry_and_succeed(self):
        calls = [0]
        async def flaky():
            calls[0] += 1
            if calls[0] < 3:
                raise TimeoutError("boom")
            return "finally"

        policy = RetryPolicy(RetryConfig(max_retries=5, base_delay_seconds=0.01))
        result = await policy.execute(flaky)
        assert result.success
        assert result.result == "finally"
        assert result.attempts == 3

    @pytest.mark.asyncio
    async def test_exhaust_retries(self):
        async def always_fails():
            raise ConnectionError("dead")

        policy = RetryPolicy(RetryConfig(max_retries=2, base_delay_seconds=0.01))
        result = await policy.execute(always_fails)
        assert not result.success
        assert result.attempts == 3  # Initial + 2 retries
        assert isinstance(result.last_error, ConnectionError)

    @pytest.mark.asyncio
    async def test_non_retryable(self):
        async def fail_value():
            raise ValueError("not retryable")

        policy = RetryPolicy(RetryConfig(max_retries=5, base_delay_seconds=0.01))
        result = await policy.execute(fail_value)
        assert not result.success
        assert result.attempts == 1  # No retry for ValueError
        assert isinstance(result.last_error, ValueError)


class TestProviderCache:
    def test_set_and_get(self):
        cache = ProviderCache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.hits == 1

    def test_miss(self):
        cache = ProviderCache()
        assert cache.get("nope") is None
        assert cache.misses == 1

    def test_ttl_expiry(self):
        cache = ProviderCache(CacheConfig(default_ttl_seconds=0))
        cache.set("key1", "value1")
        assert cache.get("key1") is None  # Expired immediately

    def test_max_entries_eviction(self):
        cache = ProviderCache(CacheConfig(max_entries=3))
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict oldest (a)
        assert cache.get("a") is None
        assert cache.size == 3

    def test_hit_rate(self):
        cache = ProviderCache()
        cache.set("a", 1)
        cache.get("a"); cache.get("a")  # 2 hits
        cache.get("b")  # 1 miss
        assert cache.hit_rate == 2/3

    def test_make_key(self):
        k1 = ProviderCache.make_key("llm", "gpt-4", "hello")
        k2 = ProviderCache.make_key("llm", "gpt-4", "hello")
        assert k1 == k2
        assert len(k1) == 32

    def test_clear(self):
        cache = ProviderCache()
        cache.set("a", 1)
        cache.clear()
        assert cache.size == 0
        assert cache.hits == 0
        assert cache.misses == 0

    def test_disabled(self):
        cache = ProviderCache(CacheConfig(enabled=False))
        cache.set("a", 1)
        assert cache.get("a") is None


class TestMetricsCollector:
    def test_record_and_snapshot(self):
        mc = MetricsCollector()
        mc.record("p1", "llm", "generate", success=True, latency_ms=100)
        mc.record("p1", "llm", "generate", success=False)
        snapshot = mc.snapshot()
        assert "p1" in snapshot
        ops = snapshot["p1"]["operations"]
        assert ops["generate"]["count"] == 2
        assert ops["generate"]["success_rate"] == 0.5

    def test_multiple_providers(self):
        mc = MetricsCollector()
        mc.record("p1", "llm", "gen", success=True)
        mc.record("p2", "embedding", "embed", success=True)
        assert mc.provider_count == 2

    def test_clear(self):
        mc = MetricsCollector()
        mc.record("p1", "llm", "gen", success=True)
        mc.clear()
        assert mc.provider_count == 0

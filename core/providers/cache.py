"""Provider Cache.

In-memory TTL cache for provider responses.
Useful for caching LLM completions, embeddings, and search results.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheConfig:
    """Cache configuration."""
    default_ttl_seconds: int = 300    # 5 minutes
    max_entries: int = 1000
    enabled: bool = True


@dataclass
class CacheEntry:
    """A single cache entry."""
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl: int = 300
    access_count: int = 0

    def is_expired(self, now: float | None = None) -> bool:
        now = now or time.time()
        return (now - self.created_at) >= self.ttl


class ProviderCache:
    """Simple in-memory TTL cache.

    Usage:
        cache = ProviderCache()
        cache.set("key", value, ttl=60)
        value = cache.get("key")
    """

    def __init__(self, config: CacheConfig | None = None) -> None:
        self._config = config or CacheConfig()
        self._store: dict[str, CacheEntry] = {}
        self._hits: int = 0
        self._misses: int = 0

    def get(self, key: str) -> Any | None:
        """Get a cached value. Returns None if missing or expired."""
        if not self._config.enabled:
            return None

        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired():
            del self._store[key]
            self._misses += 1
            return None

        entry.access_count += 1
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Store a value with TTL."""
        if not self._config.enabled:
            return

        ttl = ttl or self._config.default_ttl_seconds
        self._store[key] = CacheEntry(key=key, value=value, ttl=ttl)

        # Evict oldest if over max
        if len(self._store) > self._config.max_entries:
            oldest = min(self._store.values(), key=lambda e: e.created_at)
            del self._store[oldest.key]

    def delete(self, key: str) -> bool:
        """Delete a cached entry. Returns True if existed."""
        return self._store.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all entries."""
        self._store.clear()
        self._hits = 0
        self._misses = 0

    def expire(self) -> int:
        """Remove all expired entries. Returns count removed."""
        before = len(self._store)
        now = time.time()
        self._store = {
            k: v for k, v in self._store.items() if not v.is_expired(now)
        }
        return before - len(self._store)

    @staticmethod
    def make_key(*parts: str) -> str:
        """Create a cache key from string parts (SHA-256 hash)."""
        raw = "::".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def hits(self) -> int:
        return self._hits

    @property
    def misses(self) -> int:
        return self._misses

    @property
    def config(self) -> CacheConfig:
        return self._config

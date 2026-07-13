"""Knowledge Layer cache.

Reuses ProviderCache from core/providers/cache.py with knowledge-specific defaults.
"""

from __future__ import annotations

from core.providers.cache import ProviderCache, CacheConfig


class KnowledgeCache(ProviderCache):
    """Knowledge-specific cache with sensible defaults."""

    def __init__(self) -> None:
        super().__init__(CacheConfig(default_ttl_seconds=600, max_entries=500))

"""Mock Vector Provider using in-memory storage."""

from __future__ import annotations

import math
from typing import Any

from core.providers.vector.protocol import (
    VectorProvider, VectorRecord, VectorSearchQuery, VectorSearchResult,
)
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class MockVectorProvider(VectorProvider):
    """Mock vector store using in-memory dicts + cosine similarity.

    Collections are dict-of-dicts: {collection_name: {id: VectorRecord}}.
    """

    def __init__(self) -> None:
        info = ProviderInfo(
            provider_id="mock-vec-001",
            provider_type=ProviderType.VECTOR,
            name="mock",
            version="1.0.0",
            description="Mock vector store",
            capabilities=[
                ProviderCapability(name="search", version="1.0"),
                ProviderCapability(name="insert", version="1.0"),
            ],
        )
        super().__init__(info)
        self._collections: dict[str, dict[str, VectorRecord]] = {}

    async def _do_initialize(self) -> None:
        pass

    async def _do_shutdown(self) -> None:
        self._collections.clear()

    async def _do_health_check(self) -> bool:
        return True

    async def insert(self, collection: str, records: list[VectorRecord]) -> list[str]:
        self._require_ready()
        if collection not in self._collections:
            self._collections[collection] = {}
        coll = self._collections[collection]
        ids = []
        for r in records:
            coll[r.id] = r
            ids.append(r.id)
        return ids

    async def search(self, collection: str, query: VectorSearchQuery) -> list[VectorSearchResult]:
        self._require_ready()
        coll = self._collections.get(collection, {})
        if not coll:
            return []

        results = []
        for vid, record in coll.items():
            if query.filter:
                # Simple filter: check all filter keys match
                match = True
                for k, v in query.filter.items():
                    if record.metadata.get(k) != v:
                        match = False
                        break
                if not match:
                    continue
            score = self._cosine_similarity(query.vector, record.vector)
            if score >= query.min_score:
                results.append(VectorSearchResult(id=vid, score=score, metadata=record.metadata))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:query.top_k]

    async def delete(self, collection: str, ids: list[str]) -> int:
        self._require_ready()
        coll = self._collections.get(collection, {})
        count = 0
        for vid in ids:
            if vid in coll:
                del coll[vid]
                count += 1
        return count

    async def update(self, collection: str, record: VectorRecord) -> bool:
        self._require_ready()
        if collection not in self._collections:
            self._collections[collection] = {}
        self._collections[collection][record.id] = record
        return True

    async def collection_info(self, collection: str) -> dict[str, Any]:
        self._require_ready()
        coll = self._collections.get(collection, {})
        dim = 0
        for r in coll.values():
            dim = len(r.vector)
            break
        return {"name": collection, "count": len(coll), "dimension": dim}

    async def list_collections(self) -> list[str]:
        return list(self._collections.keys())

    async def delete_collection(self, collection: str) -> bool:
        if collection in self._collections:
            del self._collections[collection]
            return True
        return False

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

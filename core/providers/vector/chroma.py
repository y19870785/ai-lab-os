"""Chroma Vector Provider —— 真实 ChromaDB 接入。

遵循 VectorProvider Protocol，支持：
- Collection 管理
- Insert / Search / Delete / Update
- Metadata filtering
- 持久化存储
"""

from __future__ import annotations

import os
from typing import Any

from core.providers.vector.protocol import (
    VectorProvider, VectorRecord, VectorSearchQuery, VectorSearchResult,
)
from core.providers.models import ProviderCapability, ProviderInfo, ProviderType


class ChromaVectorProvider(VectorProvider):
    """ChromaDB vector store backend."""

    def __init__(
        self,
        persist_dir: str = "",
        collection_name: str = "ai_lab_knowledge",
    ) -> None:
        self._persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "data/chroma")
        self._collection_name = collection_name or os.getenv("CHROMA_COLLECTION", "ai_lab_knowledge")
        self._client = None
        self._collection = None

        info = ProviderInfo(
            provider_id="chroma-001",
            provider_type=ProviderType.VECTOR,
            name="chroma",
            version="1.4.0",
            description="ChromaDB Vector Provider",
            capabilities=[
                ProviderCapability(name="search", version="1.0"),
                ProviderCapability(name="insert", version="1.0"),
                ProviderCapability(name="delete", version="1.0"),
                ProviderCapability(name="update", version="1.0"),
                ProviderCapability(name="metadata_filter", version="1.0"),
            ],
        )
        super().__init__(info)
        self._info = info

    async def _do_initialize(self) -> None:
        try:
            import chromadb
            os.makedirs(self._persist_dir, exist_ok=True)
            self._client = chromadb.PersistentClient(path=self._persist_dir)
            # Get or create collection
            try:
                self._collection = self._client.get_collection(self._collection_name)
            except Exception:
                self._collection = self._client.create_collection(
                    name=self._collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
        except ImportError:
            raise RuntimeError("chromadb package not installed. Run: pip install chromadb")

    async def _do_shutdown(self) -> None:
        self._client = None
        self._collection = None

    async def _do_health_check(self) -> bool:
        if self._client is None:
            return False
        try:
            self._client.heartbeat()
            return True
        except Exception:
            return False

    async def insert(self, collection: str, records: list[VectorRecord]) -> list[str]:
        self._require_ready()
        coll = self._get_collection(collection)
        ids = []
        embeddings = []
        metadatas = []
        for r in records:
            ids.append(r.id)
            embeddings.append(r.vector)
            # Chroma requires non-empty metadata dict
            meta = r.metadata if r.metadata else {"source": "unknown"}
            metadatas.append(meta)
        coll.add(ids=ids, embeddings=embeddings, metadatas=metadatas)
        return ids

    async def search(self, collection: str, query: VectorSearchQuery) -> list[VectorSearchResult]:
        self._require_ready()
        coll = self._get_collection(collection)
        where = query.filter if query.filter else None
        results = coll.query(
            query_embeddings=[query.vector],
            n_results=query.top_k,
            where=where,
        )
        items = []
        if results["ids"] and results["ids"][0]:
            for i, vid in enumerate(results["ids"][0]):
                score = 1.0 - results["distances"][0][i] if results["distances"] else 0.0
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                if score >= query.min_score:
                    items.append(VectorSearchResult(id=vid, score=score, metadata=meta))
        return items

    async def delete(self, collection: str, ids: list[str]) -> int:
        self._require_ready()
        coll = self._get_collection(collection)
        try:
            coll.delete(ids=ids)
            return len(ids)
        except Exception:
            return 0

    async def update(self, collection: str, record: VectorRecord) -> bool:
        self._require_ready()
        coll = self._get_collection(collection)
        try:
            coll.upsert(
                ids=[record.id],
                embeddings=[record.vector],
                metadatas=[record.metadata],
            )
            return True
        except Exception:
            return False

    async def collection_info(self, collection: str) -> dict[str, Any]:
        self._require_ready()
        coll = self._get_collection(collection)
        return {"name": collection, "count": coll.count()}

    async def list_collections(self) -> list[str]:
        self._require_ready()
        return [c.name for c in self._client.list_collections()]

    async def delete_collection(self, collection: str) -> bool:
        self._require_ready()
        try:
            self._client.delete_collection(collection)
            return True
        except Exception:
            return False

    def _get_collection(self, name: str):
        """Get or create a collection."""
        try:
            return self._client.get_collection(name)
        except Exception:
            return self._client.create_collection(
                name=name, metadata={"hnsw:space": "cosine"},
            )

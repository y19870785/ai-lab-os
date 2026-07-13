"""SemanticMemory — Structured concept and relation memory.

Manages semantic (entity-relation) knowledge extracted from interactions.
Provides entity management and relation querying.

Usage:
    from core.memory.semantic import SemanticMemory
    from core.memory.storage.sqlite_semantic import SQLiteSemanticStore

    store = SQLiteSemanticStore("semantic.db")
    await store.initialize()
    sm = SemanticMemory(store=store, bus=get_bus())
    entity = await sm.save_entity("person", {"name": "Alice", "role": "analyst"}, importance=0.8)
    results = await sm.query(entity_type="person")
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore


class SemanticMemory:
    """High-level semantic memory manager for entity-relation storage."""

    def __init__(self, store: MemoryStore, bus=None) -> None:
        self._store = store
        self._bus = bus

    async def save_entity(
        self,
        entity_type: str,
        properties: dict[str, Any],
        entity_name: str = "",
        importance: float = 0.5,
        metadata: dict[str, Any] | None = None,
        item_id: str | None = None,
    ) -> MemoryItem:
        content = {
            "entity_type": entity_type,
            "entity_name": entity_name or properties.get("name", ""),
            "properties": properties,
        }
        item = MemoryItem(id=item_id, memory_type=MemoryType.SEMANTIC,
                          content=content, importance=importance,
                          metadata={**(metadata or {}), "action": "created"})
        await self._store.save(item)
        if self._bus:
            await self._publish("created", item.id, {"entity_type": entity_type})
        return item

    async def save_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        properties: dict[str, Any] | None = None,
        importance: float = 0.5,
        item_id: str | None = None,
    ) -> MemoryItem:
        content = {
            "relation_type": relation_type,
            "source_id": source_id,
            "target_id": target_id,
            "properties": properties or {},
        }
        item = MemoryItem(id=item_id, memory_type=MemoryType.SEMANTIC,
                          content=content, importance=importance,
                          metadata={"action": "created"})
        await self._store.save(item)
        if self._bus:
            await self._publish("created", item.id, {"relation_type": relation_type})
        return item

    async def query(
        self,
        entity_type: str | None = None,
        entity_name: str | None = None,
        relation_type: str | None = None,
        min_importance: float = 0.0,
        top_k: int = 10,
    ) -> list[MemoryItem]:
        filters: dict[str, Any] = {}
        if entity_type: filters["entity_type"] = entity_type
        if entity_name: filters["entity_name"] = entity_name
        if relation_type: filters["relation_type"] = relation_type
        q = MemoryQuery(memory_type=MemoryType.SEMANTIC, filters=filters,
                        top_k=top_k, min_importance=min_importance)
        return await self._store.query(q)

    async def get(self, entity_id: str) -> MemoryItem | None:
        return await self._store.get(entity_id)

    async def delete(self, entity_id: str) -> bool:
        r = await self._store.delete(entity_id)
        if r and self._bus:
            await self._publish("deleted", entity_id, {})
        return r

    async def count(self) -> int:
        return await self._store.count()

    @property
    def store(self) -> MemoryStore:
        return self._store

    async def _publish(self, action: str, memory_id: str, extra: dict[str, Any]) -> None:
        if not self._bus:
            return
        from core.bus import Event
        await self._bus.publish(f"memory.{action}", Event(
            event_type=f"memory.{action}", source="memory.semantic",
            payload={"memory_id": memory_id, "memory_type": "semantic", **extra},
        ))

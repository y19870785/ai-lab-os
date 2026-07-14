"""MemoryManager — Memory Layer SINGLE entry point.

业务层必须通过 MemoryManager 操作 Memory，禁止直接访问 Store。
MemoryManager 是 Memory Layer 的唯一对外接口。

Manages all four memory types (Session/Episodic/Semantic/Decision)
through a single interface. Automatically routes operations by MemoryType.
"""
from __future__ import annotations
from typing import Any
from core.memory.models import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.protocol import MemoryStore
from core.memory.session import SessionMemory
from core.errors import (
    ErrorCategory,
    FailureInfo,
    RuntimeStatus,
    failure_from_exception,
)


class MemoryManager:
    """Memory Layer unified entry point."""

    def __init__(self, bus=None):
        self._stores = {}
        self._bus = bus
        self._last_failure: FailureInfo | None = None

    def register_store(self, memory_type, store):
        self._stores[memory_type] = store

    def is_registered(self, memory_type):
        return memory_type in self._stores

    def record_failure(self, failure: FailureInfo) -> None:
        self._last_failure = failure

    def clear_failure(self) -> None:
        self._last_failure = None

    def health(self) -> dict[str, object]:
        if self._last_failure is not None:
            status = RuntimeStatus.FAILED.value
        elif not self._stores:
            status = RuntimeStatus.NOT_CONFIGURED.value
        else:
            status = RuntimeStatus.OK.value
        return {
            "status": status,
            "registered_stores": len(self._stores),
            "last_error": self._last_failure.to_dict() if self._last_failure else None,
        }

    async def health_check(self) -> dict[str, object]:
        """Probe registered stores and clear a transient failure after recovery."""
        try:
            for store in self._stores.values():
                await store.count()
        except Exception as exc:
            self.record_failure(failure_from_exception(
                exc,
                component="memory",
                operation="health_check",
                code="memory.health_check.failed",
                category=ErrorCategory.PERSISTENCE_FAILURE,
                retryable=True,
            ))
        else:
            self.clear_failure()
        return self.health()

    async def _store_call(self, operation: str, awaitable):
        try:
            result = await awaitable
        except Exception as exc:
            self.record_failure(failure_from_exception(
                exc,
                component="memory",
                operation=operation,
                code=f"memory.{operation}.failed",
                category=ErrorCategory.PERSISTENCE_FAILURE,
                retryable=True,
            ))
            raise
        self.clear_failure()
        return result

    def _get_store(self, memory_type):
        store = self._stores.get(memory_type)
        if store is None: raise ValueError(f"Store for {memory_type} not registered")
        return store

    # Unified CRUD API

    async def save_memory(self, memory_type, content, importance=0.5, item_id=None, metadata=None):
        """Save a memory item of any type. Returns memory ID."""
        item_kw = {"memory_type": memory_type, "content": content,
                   "importance": importance,
                   "metadata": {**(metadata or {}), "action": "created"}}
        if item_id is not None:
            item_kw["id"] = item_id
        item = MemoryItem(**item_kw)
        store = self._get_store(memory_type)
        memory_id = await self._store_call("save", store.save(item))
        if self._bus:
            await self._publish_event("created", memory_type.value, memory_id, {"importance": importance})
        return memory_id

    async def retrieve_memory(self, query):
        """Retrieve memories matching a query."""
        if query.memory_type:
            store = self._get_store(query.memory_type)
            results = await self._store_call("retrieve", store.query(query))
        else:
            results = []
            for store in self._stores.values():
                results.extend(await self._store_call("retrieve", store.query(query)))
            results.sort(key=lambda x: x.importance, reverse=True)
            results = results[:query.top_k]
        if self._bus and results:
            await self._publish_event("accessed", "all", "", {
                "memory_type": query.memory_type.value if query.memory_type else "all",
                "result_count": len(results),
            })
        return results

    async def search_memory(self, query_text="", memory_type=None, top_k=10):
        """Search memories by text across one or all types."""
        return await self.retrieve_memory(
            MemoryQuery(query_text=query_text, memory_type=memory_type, top_k=top_k)
        )

    async def delete_memory(self, memory_id, memory_type):
        """Delete a memory by ID and type."""
        store = self._get_store(memory_type)
        result = await self._store_call("delete", store.delete(memory_id))
        if result and self._bus:
            await self._publish_event("deleted", memory_type.value, memory_id)
        return result

    # ── Backward compatible API (deprecated) ──
    # Prefer save_memory() / retrieve_memory() / delete_memory()

    async def save(self, item):
        store = self._get_store(item.memory_type)
        item.metadata.setdefault("action", "created")
        mid = await self._store_call("save", store.save(item))
        if self._bus and item.metadata.get("_event_published") is None:
            await self._publish_event("created", item.memory_type.value, mid)
        return mid

    async def update(self, memory_id, memory_type, data):
        store = self._get_store(memory_type)
        existing = await self._store_call("get", store.get(memory_id))
        if existing is None: return None
        existing.content.update(data)
        existing.metadata["action"] = "updated"
        await self._store_call("update", store.save(existing))
        if self._bus:
            await self._publish_event("updated", memory_type.value, memory_id)
        return existing

    async def delete(self, memory_id, memory_type):
        return await self.delete_memory(memory_id, memory_type)

    async def retrieve(self, query):
        return await self.retrieve_memory(query)

    async def get(self, memory_id, memory_type):
        store = self._get_store(memory_type)
        return await self._store_call("get", store.get(memory_id))

    async def get_context(self, session_id):
        sm = self.get_session_memory()
        if sm is None: raise ValueError("SessionMemory not registered")
        return await sm.get_context(session_id)

    def get_session_memory(self):
        store = self._stores.get(MemoryType.SESSION)
        return store if isinstance(store, SessionMemory) else None

    async def count(self, memory_type=None):
        if memory_type:
            return await self._store_call(
                "count", self._get_store(memory_type).count()
            )
        total = 0
        for store in self._stores.values():
            total += await self._store_call("count", store.count())
        return total

    async def _publish_event(self, action, mt_str, memory_id, extra=None):
        if not self._bus: return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type=f"memory.{action}",
            memory_id=memory_id,
            memory_type=mt_str,
            source=f"memory.{mt_str}" if mt_str else "memory.manager",
            extra=extra,
        )
        await self._bus.publish(event.event_type, event)


_manager = None

def get_manager(bus=None):
    global _manager
    if _manager is None: _manager = MemoryManager(bus=bus)
    return _manager

def reset_manager():
    global _manager
    _manager = None

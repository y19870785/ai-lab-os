"""Session Memory 实现。

基于内存 Dict 的短期会话记忆。
支持 TTL 自动过期、Message Bus 事件集成。

使用方式：
    from core.memory.session import SessionMemory

    sm = SessionMemory(bus=get_bus())
    session = await sm.create_session(session_id="sess_001", context={"user": "张三"})
    ctx = await sm.get_context("sess_001")
    await sm.update_context("sess_001", {"preference": "保守投资"})
    await sm.delete_session("sess_001")
"""

from __future__ import annotations

import time
from typing import Any

from core.memory.models import MemoryItem, MemoryType
from core.memory.protocol import MemoryFilter, MemoryQuery, MemoryStore


class SessionMemory(MemoryStore):
    """基于内存 Dict 的会话记忆存储。

    提供会话粒度的短期记忆管理：
    - create_session：创建新会话
    - get_context：获取会话上下文
    - update_context：更新会话上下文
    - delete_session：删除会话
    - TTL 自动过期：每次访问时清理过期会话
    - Message Bus 集成：创建/更新/删除时发布事件
    """

    def __init__(
        self,
        default_ttl: int = 3600,
        bus=None,
    ) -> None:
        self._items: dict[str, MemoryItem] = {}
        self._ttl_map: dict[str, float] = {}  # id -> expire_at (timestamp)
        self._default_ttl = default_ttl
        self._bus = bus

    # ── MemoryStore lifecycle ──

    async def initialize(self) -> None:
        """No-op: SessionMemory needs no persistent init."""
        pass

    async def close(self) -> None:
        """Release all session data."""
        self._items.clear()
        self._ttl_map.clear()

    # ── Session 专用接口 ──

    async def create_session(
        self,
        session_id: str,
        context: dict[str, Any] | None = None,
        ttl: int | None = None,
    ) -> MemoryItem:
        """创建一个新的会话记忆。返回 MemoryItem。"""
        item = MemoryItem(
            id=session_id,
            memory_type=MemoryType.SESSION,
            content=context or {},
            ttl=ttl or self._default_ttl,
            metadata={"action": "created"},
        )
        await self.save(item)
        return item

    async def get_context(self, session_id: str) -> dict[str, Any] | None:
        """获取指定会话的上下文数据。如果会话不存在或已过期，返回 None。"""
        item = await self.get(session_id)
        return item.content if item else None

    async def update_context(
        self,
        session_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        """更新会话上下文。返回更新后的完整上下文。
        
        合并更新：新字段追加，已有字段覆盖。
        如果会话不存在，返回 None。
        """
        item = await self.get(session_id)
        if item is None:
            return None

        item.content.update(updates)
        item.metadata["action"] = "updated"
        await self.save(item)
        return item.content

    async def delete_session(self, session_id: str) -> bool:
        """删除指定会话。返回 True 如果存在并删除。"""
        existed = session_id in self._items or session_id in self._ttl_map
        self._items.pop(session_id, None)
        self._ttl_map.pop(session_id, None)

        if existed and self._bus:
            from core.bus.memory_events import make_memory_event
            event = make_memory_event(
                event_type="memory.deleted",
                memory_id=session_id,
                memory_type="session",
                source="memory.session",
                extra={"ttl_triggered": False},
            )
            await self._bus.publish("memory.deleted", event)

        return existed

    @property
    def active_sessions(self) -> list[str]:
        """当前活跃的会话 ID 列表（未过期）。"""
        self._evict_expired()
        return list(self._items.keys())

    @property
    def session_count(self) -> int:
        """当前活跃会话数量。"""
        self._evict_expired()
        return len(self._items)

    # ── MemoryStore 接口实现 ──

    async def save(self, item: MemoryItem) -> str:
        self._items[item.id] = item
        ttl = item.ttl or self._default_ttl
        self._ttl_map[item.id] = time.time() + ttl

        # 发布事件
        if self._bus:
            action = item.metadata.get("action", "created")
            await self._publish_event(item.id, action)

        return item.id

    async def batch_save(self, items: list[MemoryItem]) -> list[str]:
        ids = []
        for item in items:
            ids.append(await self.save(item))
        return ids

    async def get(self, id: str) -> MemoryItem | None:
        self._evict_expired()
        return self._items.get(id)

    async def query(self, spec: MemoryQuery) -> list[MemoryItem]:
        self._evict_expired()
        results = list(self._items.values())

        if spec.min_importance > 0:
            results = [r for r in results if r.importance >= spec.min_importance]

        results.sort(key=lambda x: x.importance, reverse=True)
        return results[: spec.top_k]

    async def delete(self, id: str) -> bool:
        existed = id in self._items or id in self._ttl_map
        self._items.pop(id, None)
        self._ttl_map.pop(id, None)

        if existed and self._bus:
            await self._publish_event(id, "deleted")

        return existed

    async def count(self, filter: MemoryFilter | None = None) -> int:
        self._evict_expired()
        items = list(self._items.values())
        if filter:
            if filter.min_importance > 0:
                items = [i for i in items if i.importance >= filter.min_importance]
            if filter.max_importance < 1.0:
                items = [i for i in items if i.importance <= filter.max_importance]
            if filter.time_after:
                items = [i for i in items if i.timestamp >= filter.time_after]
            if filter.time_before:
                items = [i for i in items if i.timestamp <= filter.time_before]
        return len(items)

    # ── TTL 管理 ──

    def _evict_expired(self) -> None:
        """清理所有过期的会话记忆。"""
        now = time.time()
        expired = [k for k, v in self._ttl_map.items() if v < now]
        for k in expired:
            self._items.pop(k, None)
            self._ttl_map.pop(k, None)

    # ── 事件发布 ──

    async def _publish_event(self, memory_id: str, action: str) -> None:
        """发布 Memory 事件到 Message Bus。"""
        if not self._bus:
            return
        from core.bus.memory_events import make_memory_event
        event = make_memory_event(
            event_type=f"memory.{action}",
            memory_id=memory_id,
            memory_type="session",
            source="memory.session",
            extra={"ttl_triggered": False},
        )
        await self._bus.publish(event.event_type, event)

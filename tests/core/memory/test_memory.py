"""Tests for Memory Layer core — models, session, manager."""
from __future__ import annotations
import asyncio
import pytest
from datetime import datetime, timezone

from core.memory.models import MemoryItem, MemoryType, MemoryQuery, MemoryFilter
from core.memory.session import SessionMemory
from core.memory.manager import get_manager, reset_manager
from core.bus import Event, get_bus, reset_bus


async def _make_bus():
    bus = get_bus()
    await bus.start()
    return bus


async def _make_manager(bus=None):
    if bus is None:
        bus = get_bus()
        await bus.start()
    m = get_manager(bus=bus)
    sm = SessionMemory(bus=bus)
    m.register_store(MemoryType.SESSION, sm)
    return m


# ==================== 1. Models ====================

class TestMemoryModels:
    def test_memory_item_default_fields(self):
        """MemoryItem has default values and auto-generated id."""
        item = MemoryItem(memory_type=MemoryType.SESSION, content={"key": "value"})
        assert item.id
        assert isinstance(item.id, str)
        assert len(item.id) == 32
        assert item.importance == 0.5
        assert item.timestamp is not None
        assert item.metadata == {}
        assert item.ttl is None
        assert item.embedding is None

    def test_memory_item_content_required(self):
        """content defaults to empty dict."""
        item = MemoryItem(memory_type=MemoryType.SESSION)
        assert item.content == {}

    def test_memory_type_values(self):
        """MemoryType enum has expected values."""
        assert MemoryType.SESSION.value == "session"
        assert MemoryType.EPISODIC.value == "episodic"
        assert MemoryType.SEMANTIC.value == "semantic"
        assert MemoryType.DECISION.value == "decision"

    def test_memory_query_defaults(self):
        """MemoryQuery has reasonable defaults."""
        q = MemoryQuery(memory_type=MemoryType.EPISODIC)
        assert q.top_k == 10
        assert q.offset == 0
        assert q.min_importance == 0.0
        assert q.filters == {}

    def test_memory_filter_range(self):
        """MemoryFilter supports importance and time range filtering."""
        f = MemoryFilter(min_importance=0.3, max_importance=0.8)
        assert f.min_importance == 0.3
        assert f.max_importance == 0.8
        f2 = MemoryFilter(time_after=datetime(2026, 1, 1, tzinfo=timezone.utc))
        assert f2.time_after is not None


# ==================== 2. Session Creation ====================

class TestSessionCreation:
    @pytest.mark.asyncio
    async def test_create_session(self):
        session_memory = SessionMemory(default_ttl=3600)
        session = await session_memory.create_session(
            "sess_001", context={"user": "zhangsan", "topic": "investment"},
        )
        assert session.id == "sess_001"
        assert session.memory_type == MemoryType.SESSION
        assert session.content["user"] == "zhangsan"
        assert session.content["topic"] == "investment"

    @pytest.mark.asyncio
    async def test_create_session_without_context(self):
        session_memory = SessionMemory(default_ttl=3600)
        session = await session_memory.create_session("sess_002")
        assert session.id == "sess_002"
        assert session.content == {}

    @pytest.mark.asyncio
    async def test_session_id_unique(self):
        session_memory = SessionMemory(default_ttl=3600)
        s1 = await session_memory.create_session("sess_a")
        s2 = await session_memory.create_session("sess_b")
        assert s1.id != s2.id

    @pytest.mark.asyncio
    async def test_create_session_default_ttl(self):
        sm = SessionMemory(default_ttl=600)
        session = await sm.create_session("sess_ttl")
        assert session.ttl == 600


# ==================== 3. Session Access ====================

class TestSessionAccess:
    @pytest.mark.asyncio
    async def test_get_context_returns_content(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001", context={"user": "zhangsan", "count": 5})
        ctx = await session_memory.get_context("sess_001")
        assert ctx is not None
        assert ctx["user"] == "zhangsan"
        assert ctx["count"] == 5

    @pytest.mark.asyncio
    async def test_get_context_nonexistent(self):
        session_memory = SessionMemory(default_ttl=3600)
        ctx = await session_memory.get_context("nonexistent")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_get_returns_memory_item(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001")
        item = await session_memory.get("sess_001")
        assert item is not None
        assert isinstance(item, MemoryItem)
        assert item.memory_type == MemoryType.SESSION


# ==================== 4. Session Update ====================

class TestSessionUpdate:
    @pytest.mark.asyncio
    async def test_update_context_merge(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001", context={"user": "zhangsan"})
        updated = await session_memory.update_context("sess_001", {"topic": "stock_analysis"})
        assert updated is not None
        assert updated["user"] == "zhangsan"
        assert updated["topic"] == "stock_analysis"

    @pytest.mark.asyncio
    async def test_update_context_overwrite(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001", context={"user": "zhangsan"})
        updated = await session_memory.update_context("sess_001", {"user": "lisi"})
        assert updated["user"] == "lisi"

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self):
        session_memory = SessionMemory(default_ttl=3600)
        result = await session_memory.update_context("nonexistent", {"key": "val"})
        assert result is None

    @pytest.mark.asyncio
    async def test_save_method_in_memory_store(self):
        session_memory = SessionMemory(default_ttl=3600)
        item = MemoryItem(memory_type=MemoryType.SESSION, content={"msg": "test"})
        mid = await session_memory.save(item)
        assert mid == item.id
        retrieved = await session_memory.get(item.id)
        assert retrieved is not None
        assert retrieved.content["msg"] == "test"


# ==================== 5. Session Delete ====================

class TestSessionDelete:
    @pytest.mark.asyncio
    async def test_delete_session(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001")
        assert "sess_001" in session_memory.active_sessions
        result = await session_memory.delete_session("sess_001")
        assert result is True
        assert "sess_001" not in session_memory.active_sessions

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self):
        session_memory = SessionMemory(default_ttl=3600)
        result = await session_memory.delete_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_context_gone_after_delete(self):
        session_memory = SessionMemory(default_ttl=3600)
        await session_memory.create_session("sess_001", context={"key": "val"})
        await session_memory.delete_session("sess_001")
        ctx = await session_memory.get_context("sess_001")
        assert ctx is None

    @pytest.mark.asyncio
    async def test_delete_via_store_interface(self):
        session_memory = SessionMemory(default_ttl=3600)
        item = MemoryItem(memory_type=MemoryType.SESSION, content={})
        mid = await session_memory.save(item)
        assert await session_memory.delete(mid) is True
        assert await session_memory.get(mid) is None


# ==================== 6. TTL ====================

class TestSessionTTL:
    @pytest.mark.asyncio
    async def test_ttl_default_used(self):
        sm = SessionMemory(default_ttl=3600)
        session = await sm.create_session("sess_001")
        assert session.ttl == 3600

    @pytest.mark.asyncio
    async def test_ttl_override(self):
        sm = SessionMemory(default_ttl=3600)
        session = await sm.create_session("sess_001", ttl=60)
        assert session.ttl == 60

    @pytest.mark.asyncio
    async def test_eviction_on_get(self):
        sm = SessionMemory(default_ttl=1)
        await sm.create_session("sess_001")
        assert "sess_001" in sm.active_sessions
        await asyncio.sleep(1.5)
        item = await sm.get("sess_001")
        assert item is None

    @pytest.mark.asyncio
    async def test_eviction_on_active_sessions(self):
        sm = SessionMemory(default_ttl=1)
        await sm.create_session("sess_001")
        await asyncio.sleep(1.5)
        assert sm.session_count == 0
        assert sm.active_sessions == []


# ==================== 7. Events ====================

class TestSessionEvents:
    @pytest.mark.asyncio
    async def test_create_session_emits_event(self):
        bus = await _make_bus()
        received: list[Event] = []
        async def handler(event: Event):
            received.append(event)
        await bus.subscribe("memory.created", handler)
        sm = SessionMemory(bus=bus)
        await sm.create_session("sess_001")
        await asyncio.sleep(0.05)
        assert len(received) >= 1
        assert received[0].payload["memory_id"] == "sess_001"

    @pytest.mark.asyncio
    async def test_update_emits_event(self):
        bus = await _make_bus()
        received: list[Event] = []
        async def handler(event: Event):
            received.append(event)
        await bus.subscribe("memory.updated", handler)
        sm = SessionMemory(bus=bus)
        await sm.create_session("sess_001")
        await sm.update_context("sess_001", {"key": "value"})
        await asyncio.sleep(0.05)
        updated_events = [e for e in received if e.event_type == "memory.updated"]
        assert len(updated_events) >= 1

    @pytest.mark.asyncio
    async def test_delete_emits_event(self):
        bus = await _make_bus()
        received: list[Event] = []
        async def handler(event: Event):
            received.append(event)
        await bus.subscribe("memory.deleted", handler)
        sm = SessionMemory(bus=bus)
        await sm.create_session("sess_001")
        await sm.delete_session("sess_001")
        await asyncio.sleep(0.05)
        deleted = [e for e in received if e.event_type == "memory.deleted"]
        assert len(deleted) == 1
        assert deleted[0].payload["memory_id"] == "sess_001"

    @pytest.mark.asyncio
    async def test_manager_save_emits_event(self):
        bus = await _make_bus()
        received: list[Event] = []
        async def handler(event: Event):
            received.append(event)
        await bus.subscribe("memory.created", handler)
        sm = SessionMemory(bus=bus)
        m = get_manager(bus=bus)
        m.register_store(MemoryType.SESSION, sm)
        await m.save(MemoryItem(id="sess_001", memory_type=MemoryType.SESSION, content={"msg": "hello"}))
        await asyncio.sleep(0.05)
        created = [e for e in received if e.event_type == "memory.created"]
        assert len(created) >= 1


# ==================== 8. MemoryManager ====================

class TestMemoryManager:
    @pytest.mark.asyncio
    async def test_save_and_retrieve(self):
        bus = await _make_bus()
        manager = await _make_manager(bus)
        memory_id = await manager.save(MemoryItem(memory_type=MemoryType.SESSION, content={"msg": "hello world"}))
        assert memory_id is not None
        results = await manager.retrieve(MemoryQuery(memory_type=MemoryType.SESSION))
        assert len(results) >= 1
        assert results[0].content["msg"] == "hello world"

    @pytest.mark.asyncio
    async def test_retrieve_with_filter(self):
        bus = await _make_bus()
        manager = await _make_manager(bus)
        await manager.save(MemoryItem(memory_type=MemoryType.SESSION, content={"type": "session"}))
        with pytest.raises(ValueError, match="not registered"):
            await manager.retrieve(MemoryQuery(memory_type=MemoryType.EPISODIC))

    @pytest.mark.asyncio
    async def test_get_by_id(self):
        bus = await _make_bus()
        manager = await _make_manager(bus)
        await manager.save(MemoryItem(id="test_id", memory_type=MemoryType.SESSION, content={"msg": "test"}))
        item = await manager.get("test_id", MemoryType.SESSION)
        assert item is not None
        assert item.content["msg"] == "test"

    @pytest.mark.asyncio
    async def test_count(self):
        bus = await _make_bus()
        manager = await _make_manager(bus)
        c1 = await manager.count(MemoryType.SESSION)
        await manager.save(MemoryItem(memory_type=MemoryType.SESSION, content={}))
        c2 = await manager.count(MemoryType.SESSION)
        assert c2 == c1 + 1

    @pytest.mark.asyncio
    async def test_global_singleton(self):
        reset_manager()
        m1 = get_manager()
        m2 = get_manager()
        assert m1 is m2

    @pytest.mark.asyncio
    async def test_get_context_shortcut(self):
        bus = await _make_bus()
        manager = await _make_manager(bus)
        sm = manager.get_session_memory()
        assert sm is not None
        await sm.create_session("sess_001", context={"user": "zhangsan"})
        ctx = await manager.get_context("sess_001")
        assert ctx is not None
        assert ctx["user"] == "zhangsan"

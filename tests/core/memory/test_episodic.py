"""Episodic Memory unit tests - clean version."""
from __future__ import annotations
import asyncio
import os as _os
import tempfile
from datetime import datetime, timedelta
from typing import Any
import pytest
from core.bus import Event, get_bus, reset_bus
from core.memory import MemoryFilter, MemoryItem, MemoryQuery, MemoryType
from core.memory.consolidation import ConsolidationEngine
from core.memory.decay import DecayConfig, MemoryDecay
from core.memory.episodic import EpisodicMemory
from core.memory.importance import ImportanceScorer
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore


def _db():
    fd, p = tempfile.mkstemp(suffix=".db")
    _os.close(fd)
    return p

def _cl(p):
    try: _os.unlink(p)
    except: pass

async def _mk_store(p):
    s = SQLiteEpisodicStore(db_path=p)
    await s.initialize()
    return s

async def _mk_bus():
    reset_bus(); b = get_bus(); await b.start(); return b

def _mk_item(imp=0.5, sid="ts", aid="ta", txt="te", iid=None):
    c = {"session_id": sid, "agent_id": aid, "events": [{"type": "msg", "content": txt}], "summary": txt}
    if iid is not None:
        return MemoryItem(id=iid, memory_type=MemoryType.EPISODIC, content=c, importance=imp)
    return MemoryItem(memory_type=MemoryType.EPISODIC, content=c, importance=imp)


class TestStore:
    @pytest.mark.asyncio
    async def test_save_and_get(self):
        p = _db(); st = await _mk_store(p)
        await st.save(_mk_item(iid="e1")); r = await st.get("e1")
        assert r is not None and r.id == "e1"
        _cl(p)

    @pytest.mark.asyncio
    async def test_save_generates_id(self):
        p = _db(); st = await _mk_store(p)
        iid = await st.save(_mk_item(iid="g1"))
        assert iid == "g1"
        _cl(p)

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        p = _db(); st = await _mk_store(p)
        assert await st.get("x") is None
        _cl(p)

    @pytest.mark.asyncio
    async def test_delete(self):
        p = _db(); st = await _mk_store(p)
        await st.save(_mk_item(iid="d1"))
        assert await st.delete("d1") is True
        _cl(p)

    @pytest.mark.asyncio
    async def test_count(self):
        p = _db(); st = await _mk_store(p)
        assert await st.count() == 0
        await st.save(_mk_item(iid="c1")); await st.save(_mk_item(iid="c2"))
        assert await st.count() == 2
        _cl(p)

    @pytest.mark.asyncio
    async def test_batch_save(self):
        p = _db(); st = await _mk_store(p)
        ids = await st.batch_save([_mk_item(iid="b1"), _mk_item(iid="b2")])
        assert ids == ["b1", "b2"]
        _cl(p)

    @pytest.mark.asyncio
    async def test_importance_filter(self):
        p = _db(); st = await _mk_store(p)
        await st.save(_mk_item(iid="lo", imp=0.1))
        await st.save(_mk_item(iid="hi", imp=0.9))
        q = MemoryQuery(memory_type=MemoryType.EPISODIC, min_importance=0.5, top_k=10)
        assert all(r.importance >= 0.5 for r in await st.query(q))
        _cl(p)

    @pytest.mark.asyncio
    async def test_time_range(self):
        p = _db(); st = await _mk_store(p); now = datetime.now()
        old = _mk_item(iid="o"); old.timestamp = now - timedelta(days=10)
        new = _mk_item(iid="n"); new.timestamp = now
        await st.save(old); await st.save(new)
        q = MemoryQuery(memory_type=MemoryType.EPISODIC, time_range=(now - timedelta(days=3), now), top_k=10)
        assert len(await st.query(q)) == 1
        _cl(p)

    @pytest.mark.asyncio
    async def test_session_filter(self):
        p = _db(); st = await _mk_store(p)
        await st.save(_mk_item(iid="a1", sid="A")); await st.save(_mk_item(iid="a2", sid="A"))
        await st.save(_mk_item(iid="b1", sid="B"))
        q = MemoryQuery(memory_type=MemoryType.EPISODIC, filters={"session_id": "A"}, top_k=10)
        assert len(await st.query(q)) == 2
        _cl(p)

    @pytest.mark.asyncio
    async def test_top_k(self):
        p = _db(); st = await _mk_store(p)
        for i in range(20): await st.save(_mk_item(iid=f"l_{i}"))
        assert len(await st.query(MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=5))) == 5
        _cl(p)

    @pytest.mark.asyncio
    async def test_vacuum(self):
        p = _db(); st = await _mk_store(p)
        await st.save(_mk_item(iid="v1")); await st.delete("v1"); await st.vacuum()
        _cl(p)


class TestEpisodicAPI:
    @pytest.mark.asyncio
    async def test_save_episode(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        item = await ep.save_episode("s1", "a1", [{"t": "x"}], "test", importance=0.8, item_id="se1")
        assert item.memory_type == MemoryType.EPISODIC and item.importance == 0.8
        _cl(p)

    @pytest.mark.asyncio
    async def test_retrieve_by_id(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        await ep.save_episode("s1", "a1", [], "r", item_id="rid")
        assert len(await ep.retrieve_episode(episode_id="rid")) == 1
        _cl(p)

    @pytest.mark.asyncio
    async def test_retrieve_by_session(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        await ep.save_episode("sg", "a1", [], "f", item_id="g1")
        await ep.save_episode("sg", "a2", [], "s", item_id="g2")
        await ep.save_episode("ot", "a3", [], "o", item_id="g3")
        assert len(await ep.retrieve_episode(session_id="sg")) == 2
        _cl(p)

    @pytest.mark.asyncio
    async def test_delete(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        await ep.save_episode("s1", "a", [], "d", item_id="dm")
        assert await ep.delete("dm") is True
        _cl(p)

    @pytest.mark.asyncio
    async def test_delete_by_session(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        await ep.save_episode("dg", "a", [], "d1", item_id="d1")
        await ep.save_episode("dg", "a", [], "d2", item_id="d2")
        await ep.save_episode("km", "a", [], "k1", item_id="k1")
        assert await ep.delete_by_session("dg") == 2
        assert await s.get("k1") is not None
        _cl(p)

    @pytest.mark.asyncio
    async def test_count(self):
        p = _db(); s = await _mk_store(p); ep = EpisodicMemory(store=s)
        assert await ep.count() == 0
        await ep.save_episode("s1", "a", [], "c1", item_id="cnt1")
        assert await ep.count() == 1
        _cl(p)


class TestEvents:
    @pytest.mark.asyncio
    async def test_save_emits_created(self):
        p = _db(); s = await _mk_store(p); bus = await _mk_bus(); rcv = []
        async def h(e): rcv.append(e)
        await bus.subscribe("memory.created", h)
        try:
            ep = EpisodicMemory(store=s, bus=bus)
            await ep.save_episode("s1", "a", [], "t", item_id="ev1")
            await asyncio.sleep(0.05)
            assert rcv[0].event_type == "memory.created"
        finally:
            await bus.stop(); reset_bus()
        _cl(p)


class TestConsolidation:
    @pytest.mark.asyncio
    async def test_consolidation_cycle(self):
        p = _db(); s = await _mk_store(p)
        eng = ConsolidationEngine()
        eng.register_store(MemoryType.EPISODIC, s)
        await s.save(_mk_item(iid="ch", imp=0.9))
        await s.save(_mk_item(iid="cl", imp=0.1))
        assert (await eng.run_cycle()).evaluated == 2
        _cl(p)

    @pytest.mark.asyncio
    async def test_importance_scorer(self):
        p = _db(); s = await _mk_store(p)
        item = _mk_item(imp=0.7, iid="is1"); await s.save(item)
        assert 0.0 <= ImportanceScorer().calculate(item) <= 1.0
        _cl(p)

    @pytest.mark.asyncio
    async def test_decay(self):
        p = _db(); s = await _mk_store(p)
        item = _mk_item(imp=0.8, iid="de1"); await s.save(item)
        assert 0.0 <= MemoryDecay().effective_strength(item, 0.8) <= 1.0
        _cl(p)
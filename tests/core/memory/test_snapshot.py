"""Memory Snapshot tests."""
from __future__ import annotations
import asyncio, tempfile, os
import pytest
from core.memory import MemoryItem, MemoryQuery, MemoryType, get_manager, reset_manager
from core.memory.snapshot import MemorySnapshot
from core.database import get_db, reset_db, run_all_migrations

async def _setup():
    reset_manager(); reset_db()
    p = tempfile.mkdtemp()
    db = get_db(p)
    run_all_migrations(db)
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.storage.sqlite_semantic import SQLiteSemanticStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    mgr = get_manager()
    es = SQLiteEpisodicStore(db_path=os.path.join(p, "ep.db")); await es.initialize()
    mgr.register_store(MemoryType.EPISODIC, es)
    ss = SQLiteSemanticStore(db_path=os.path.join(p, "sem.db")); await ss.initialize()
    mgr.register_store(MemoryType.SEMANTIC, ss)
    return mgr, db, p

class TestSnapshot:
    @pytest.mark.asyncio
    async def test_create_snapshot(self):
        mgr, db, p = await _setup()
        stores = mgr._stores
        snap = MemorySnapshot(stores, db_manager=db)
        sid = await snap.create_snapshot(label="test1")
        assert len(sid) > 0
        conn = db.get_connection("snapshot")
        r = conn.execute("SELECT count(*) FROM snapshots").fetchone()
        assert r[0] == 1
        reset_manager(); reset_db()


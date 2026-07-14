"""SP-003 SQLite connection ownership and transaction tests."""

from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from core.database import DatabaseManager, DatabasePathConflictError
from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.storage.sqlite_semantic import SQLiteSemanticStore


STORE_CASES = (
    ("episodic", MemoryType.EPISODIC, SQLiteEpisodicStore, "episodic_memories"),
    ("semantic", MemoryType.SEMANTIC, SQLiteSemanticStore, "semantic_memories"),
    ("decision", MemoryType.DECISION, SQLiteDecisionStore, "decision_memories"),
)


def make_item(memory_type: MemoryType, suffix: str = "one") -> MemoryItem:
    return MemoryItem(
        memory_type=memory_type,
        content={"value": suffix},
        metadata={"source": "sp-003-test"},
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("name,memory_type,store_type,table", STORE_CASES)
async def test_managed_store_borrows_connection_without_closing_it(
    tmp_path: Path, name, memory_type, store_type, table
):
    db_path = tmp_path / f"{name}.db"
    manager = DatabaseManager(tmp_path)
    store = store_type(str(db_path), db_manager=manager)

    await store.initialize()
    item = make_item(memory_type)
    await store.save(item)
    shared = manager.get_connection(name)
    assert shared.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 1

    await store.close()
    assert shared.execute("SELECT 1").fetchone()[0] == 1
    assert manager.get_path(name) == db_path.resolve()
    manager.close_all()


@pytest.mark.parametrize("name", ("episodic", "semantic", "decision"))
def test_close_removes_connection_and_explicit_get_reopens(name: str, tmp_path: Path):
    manager = DatabaseManager(tmp_path)
    old = manager.get_connection(name)
    manager.close(name)

    with pytest.raises(sqlite3.ProgrammingError):
        old.execute("SELECT 1")

    reopened = manager.get_connection(name)
    assert reopened is not old
    assert reopened.execute("SELECT 1").fetchone()[0] == 1
    manager.close_all()
    manager.close_all()
    assert manager.connection_count == 0


def test_externally_closed_cached_connection_is_never_returned(tmp_path: Path):
    manager = DatabaseManager(tmp_path)
    stale = manager.get_connection("episodic")
    stale.close()

    reopened = manager.get_connection("episodic")

    assert reopened is not stale
    assert reopened.execute("SELECT 1").fetchone()[0] == 1
    manager.close_all()


def test_logical_name_cannot_be_rebound(tmp_path: Path):
    manager = DatabaseManager(tmp_path)
    manager.get_connection("episodic", tmp_path / "episodic.db")
    with pytest.raises(DatabasePathConflictError):
        manager.get_connection("episodic", tmp_path / "other.db")
    manager.close_all()


def test_health_probe_does_not_create_database(tmp_path: Path):
    manager = DatabaseManager(tmp_path)
    assert manager.health_check("missing") is False
    assert manager.health()["status"] == "not_initialized"
    assert not (tmp_path / "missing.db").exists()


def test_close_all_attempts_every_connection_before_reporting_failure(tmp_path: Path):
    closed: list[str] = []

    class FakeConnection:
        def __init__(self, name: str, fail: bool = False):
            self.name = name
            self.fail = fail

        def close(self):
            closed.append(self.name)
            if self.fail:
                raise sqlite3.OperationalError("injected close failure")

    manager = DatabaseManager(tmp_path)
    manager._connections = {
        "failing": FakeConnection("failing", fail=True),
        "healthy": FakeConnection("healthy"),
    }

    with pytest.raises(RuntimeError, match="Failed to close 1 database"):
        manager.close_all()

    assert closed == ["failing", "healthy"]
    assert manager.connection_count == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("name,memory_type,store_type,table", STORE_CASES)
async def test_standalone_store_keeps_full_api_and_closes_owned_lease(
    tmp_path: Path, name, memory_type, store_type, table
):
    store = store_type(str(tmp_path / f"{name}.db"))
    await store.initialize()
    item = make_item(memory_type)
    assert await store.save(item) == item.id
    assert (await store.get(item.id)).content == item.content
    assert [found.id for found in await store.query(
        MemoryQuery(memory_type=memory_type, top_k=10)
    )] == [item.id]
    assert await store.count() == 1
    assert await store.delete(item.id) is True
    assert await store.count() == 0

    lease = store._lease()
    assert lease.owned is True
    with lease as conn:
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    with pytest.raises(sqlite3.ProgrammingError):
        lease.connection.execute("SELECT 1")


@pytest.mark.asyncio
@pytest.mark.parametrize("name,memory_type,store_type,table", STORE_CASES)
async def test_batch_save_is_atomic_on_serialization_failure(
    tmp_path: Path, name, memory_type, store_type, table
):
    manager = DatabaseManager(tmp_path)
    store = store_type(str(tmp_path / f"{name}.db"), db_manager=manager)
    await store.initialize()
    good = make_item(memory_type, "good")
    bad = make_item(memory_type, "bad")
    bad.content["not_json"] = object()

    with pytest.raises(TypeError):
        await store.batch_save([good, bad])

    assert await store.count() == 0
    assert manager.get_connection(name).execute(
        f"SELECT COUNT(*) FROM {table}"
    ).fetchone()[0] == 0
    manager.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("name,memory_type,store_type,_table", STORE_CASES)
async def test_save_failure_rolls_back_and_connection_remains_reusable(
    tmp_path: Path, name, memory_type, store_type, _table
):
    manager = DatabaseManager(tmp_path)
    store = store_type(str(tmp_path / f"{name}.db"), db_manager=manager)
    await store.initialize()
    invalid = make_item(memory_type, "invalid")
    invalid.content["not_json"] = object()

    with pytest.raises(TypeError):
        await store.save(invalid)

    conn = manager.get_connection(name)
    assert conn.in_transaction is False
    valid = make_item(memory_type, "valid")
    await store.save(valid)
    assert await store.count() == 1
    manager.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("name,memory_type,store_type,_table", STORE_CASES)
async def test_successful_batch_commits_every_item(
    tmp_path: Path, name, memory_type, store_type, _table
):
    manager = DatabaseManager(tmp_path)
    store = store_type(str(tmp_path / f"{name}.db"), db_manager=manager)
    await store.initialize()
    items = [make_item(memory_type, str(index)) for index in range(3)]
    assert await store.batch_save(items) == [item.id for item in items]
    assert await store.count() == 3
    manager.close_all()


@pytest.mark.asyncio
async def test_existing_database_is_read_without_path_or_schema_drift(tmp_path: Path):
    db_path = tmp_path / "episodic.db"
    standalone = SQLiteEpisodicStore(str(db_path))
    await standalone.initialize()
    item = make_item(MemoryType.EPISODIC, "existing")
    await standalone.save(item)

    with sqlite3.connect(db_path) as conn:
        before = conn.execute("PRAGMA table_info(episodic_memories)").fetchall()

    manager = DatabaseManager(tmp_path / "database")
    managed = SQLiteEpisodicStore(str(db_path), db_manager=manager)
    await managed.initialize()
    found = await managed.get(item.id)
    with manager.lease("episodic") as conn:
        after = [
            tuple(row)
            for row in conn.execute("PRAGMA table_info(episodic_memories)").fetchall()
        ]

    assert found is not None and found.content == item.content
    assert before == after
    assert manager.get_path("episodic") == db_path.resolve()
    assert not (tmp_path / "database" / "episodic.db").exists()
    manager.close_all()


@pytest.mark.asyncio
async def test_shared_connection_concurrent_writes_complete_without_deadlock(tmp_path: Path):
    manager = DatabaseManager(tmp_path)
    store = SQLiteEpisodicStore(
        str(tmp_path / "episodic.db"), db_manager=manager
    )
    await store.initialize()

    def save(index: int) -> None:
        asyncio.run(store.save(make_item(MemoryType.EPISODIC, str(index))))

    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [loop.run_in_executor(executor, save, index) for index in range(40)]
        await asyncio.wait_for(asyncio.gather(*futures), timeout=10)

    assert await store.count() == 40
    manager.close_all()

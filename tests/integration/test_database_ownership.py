"""SP-003 composition and shutdown acceptance tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.system import create_system, make_test_settings
from core.system.exceptions import SystemInitializationError

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_composition_root_injects_one_manager_and_preserves_paths(tmp_path: Path):
    settings = make_test_settings(tmp_path)
    system = await create_system(settings)
    managed_stores = system.memory_stores[1:]

    assert all(store._db_manager is system.database_manager for store in managed_stores)
    await system.start()
    try:
        assert system.database_manager.connection_count == 4
        assert system.database_manager.get_path("episodic") == (
            settings.sqlite_dir / "episodic.db"
        ).resolve()
        assert system.database_manager.get_path("user_tasks") == (
            settings.sqlite_dir / "tasks.db"
        ).resolve()
        assert not (settings.data_dir / "database" / "episodic.db").exists()
        assert (await system.health())["components"]["database"]["status"] == "healthy"
    finally:
        await system.shutdown()


async def test_system_shutdown_closes_every_managed_connection(tmp_path: Path):
    system = await create_system(make_test_settings(tmp_path))
    await system.start()
    connections = [
        system.database_manager.get_connection(name)
        for name in ("episodic", "semantic", "decision", "user_tasks")
    ]

    await system.shutdown()
    await system.shutdown()
    assert system.database_manager.connection_count == 0
    for conn in connections:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


async def test_partial_memory_startup_failure_closes_open_connections(
    tmp_path: Path, monkeypatch
):
    system = await create_system(make_test_settings(tmp_path))
    semantic_store = system.memory_stores[2]
    opened: list[sqlite3.Connection] = []

    async def fail_after_episodic_opened():
        opened.append(system.database_manager.get_connection("episodic"))
        raise sqlite3.OperationalError("injected semantic initialization failure")

    monkeypatch.setattr(semantic_store, "initialize", fail_after_episodic_opened)
    with pytest.raises(SystemInitializationError, match="injected semantic"):
        await system.start()

    assert system.database_manager.connection_count == 0
    assert opened
    with pytest.raises(sqlite3.ProgrammingError):
        opened[0].execute("SELECT 1")

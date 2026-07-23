"""SQLite Work Log codec, isolation, pagination, and read-only tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from core.database.manager import DatabaseManager
from core.memory.models import MemoryItem, MemoryType
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.work_log import (
    SQLiteWorkLogRepository,
    WorkLogContextRef,
    WorkLogQuery,
    WorkLogRecord,
    WorkLogSource,
)
from core.work_log.errors import (
    WorkLogConflictError,
    WorkLogLegacyProjectionError,
    WorkLogWorkspaceMismatchError,
)
from core.workspace.models import WorkspaceKey

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


async def _repository(tmp_path):
    path = tmp_path / "episodic.db"
    manager = DatabaseManager(tmp_path)
    store = SQLiteEpisodicStore(str(path), db_manager=manager)
    await store.initialize()
    repository = SQLiteWorkLogRepository(
        manager, path, timezone_name="Asia/Shanghai"
    )
    await repository.initialize()
    return manager, store, repository


def _record(identifier, workspace, *, subject="完成验货", delta=0):
    return WorkLogRecord(
        id=identifier,
        workspace_key=workspace,
        occurred_at=NOW + timedelta(minutes=delta),
        timezone="Asia/Shanghai",
        subject=subject,
        raw_text=subject,
        target="张经理",
        tags=("蜂蜡", "QA"),
        source=WorkLogSource.API,
        context_refs=[
            WorkLogContextRef(kind="inbox", target_id="inbox_source")
        ],
        created_at=NOW,
        schema_version=1,
    )


@pytest.mark.asyncio
async def test_canonical_create_get_filters_pagination_and_insert_only(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    workspace = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    first = _record("wl_" + "1" * 32, workspace)
    second = _record("wl_" + "2" * 32, workspace, subject="跟进报价")
    try:
        stored_first = await repository.create(first)
        await repository.create(second)
        with pytest.raises(WorkLogConflictError):
            await repository.create(first)
        page = await repository.list(
            workspace,
            WorkLogQuery(
                target="张经理",
                tags=["QA"],
                text="完成",
                context_ref="inbox_source",
                limit=1,
            ),
        )
        assert page.items == (stored_first,)
        assert page.total_count == 1
        assert await repository.get(workspace, first.id) == stored_first
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_full_workspace_isolation_and_no_schema_change(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    alpha = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    before = None
    try:
        with manager.lease("episodic") as conn:
            before = tuple(
                conn.execute(
                    "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
                ).fetchall()
            )
        record = _record("wl_" + "3" * 32, alpha)
        await repository.create(record)
        for mismatch in (
            WorkspaceKey(
                tenant_id="other", workspace_id="alpha", namespace="ops"
            ),
            WorkspaceKey(
                tenant_id="tenant", workspace_id="other", namespace="ops"
            ),
            WorkspaceKey(
                tenant_id="tenant", workspace_id="alpha", namespace="other"
            ),
        ):
            with pytest.raises(WorkLogWorkspaceMismatchError):
                await repository.get(mismatch, record.id)
            assert (await repository.list(mismatch, WorkLogQuery())).items == ()
        with manager.lease("episodic") as conn:
            after = tuple(
                conn.execute(
                    "SELECT type,name,sql FROM sqlite_master ORDER BY type,name"
                ).fetchall()
            )
        assert after == before
        assert not (tmp_path / "work_logs.db").exists()
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_legacy_projection_is_stable_and_query_is_zero_write(tmp_path):
    manager, store, repository = await _repository(tmp_path)
    legacy = MemoryItem(
        id="random-memory-id",
        memory_type=MemoryType.EPISODIC,
        content={
            "type": "work_log",
            "date": "2026-07-23",
            "subject": "历史记录",
            "status": "unknown",
            "tags": ["legacy"],
        },
        timestamp=NOW,
    )
    try:
        await store.save(legacy)
        with manager.lease("episodic") as conn:
            before = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )
        page = await repository.list(WorkspaceKey(), WorkLogQuery())
        projected = page.items[0]
        assert projected.id.startswith("wl_legacy_")
        assert projected.legacy_memory_id == legacy.id
        assert projected.legacy_raw_status == "unknown"
        assert await repository.get(WorkspaceKey(), projected.id) == projected
        with manager.lease("episodic") as conn:
            after = tuple(
                tuple(row)
                for row in conn.execute(
                    "SELECT * FROM episodic_memories ORDER BY id"
                ).fetchall()
            )
        assert after == before
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_malformed_legacy_fails_closed(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    try:
        with manager.lease("episodic") as conn:
            conn.execute(
                """
                INSERT INTO episodic_memories
                (id,memory_type,content,importance,timestamp,metadata)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    "bad-row",
                    "episodic",
                    json.dumps({"type": "work_log", "date": "not-a-date"}),
                    0.5,
                    "not-a-date",
                    "{}",
                ),
            )
            conn.commit()
        with pytest.raises(WorkLogLegacyProjectionError) as failure:
            await repository.list(WorkspaceKey(), WorkLogQuery())
        assert failure.value.field == "occurred_at"
        assert "bad-row" not in failure.value.row_digest
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_exact_pagination_has_no_candidate_cap_and_stable_tie_break(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    workspace = WorkspaceKey()
    try:
        with manager.lease("episodic") as conn:
            rows = []
            for index in range(205):
                identifier = f"wl_{index:032x}"
                content = {
                    "type": "work_log",
                    "schema_version": 1,
                    "metadata": {
                        "tenant_id": "default",
                        "workspace_id": "default",
                        "namespace": "default",
                    },
                    "occurred_at": NOW.isoformat(),
                    "timezone": "UTC",
                    "subject": f"record {index}",
                    "raw_text": f"record {index}",
                    "target": None,
                    "status": "completed",
                    "tags": [],
                    "source": "api",
                    "context_refs": [],
                }
                rows.append(
                    (
                        identifier,
                        "episodic",
                        json.dumps(content),
                        0.6,
                        NOW.isoformat(),
                        "{}",
                    )
                )
            conn.executemany(
                """
                INSERT INTO episodic_memories
                (id,memory_type,content,importance,timestamp,metadata)
                VALUES (?,?,?,?,?,?)
                """,
                rows,
            )
            conn.commit()
        first = await repository.list(
            workspace, WorkLogQuery(limit=200, offset=0)
        )
        second = await repository.list(
            workspace, WorkLogQuery(limit=200, offset=200)
        )
        assert first.total_count == 205
        assert first.count == 200 and first.has_more is True
        assert second.count == 5 and second.has_more is False
        identifiers = [item.id for item in (*first.items, *second.items)]
        assert identifiers == sorted(identifiers, reverse=True)
        assert len(set(identifiers)) == 205
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_standalone_repository_closes_only_its_own_manager(tmp_path):
    path = tmp_path / "episodic.db"
    store = SQLiteEpisodicStore(str(path))
    await store.initialize()
    await store.close()
    standalone = SQLiteWorkLogRepository(
        db_path=path, timezone_name="Asia/Shanghai"
    )
    await standalone.initialize()
    assert (await standalone.health_check())["status"] == "healthy"
    await standalone.close()
    assert (await standalone.health_check())["status"] == "not_initialized"

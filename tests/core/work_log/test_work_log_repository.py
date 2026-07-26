"""SQLite Work Log codec, isolation, pagination, and read-only tests."""

from __future__ import annotations

import json
import hashlib
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
    WorkLogNotFoundError,
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


def _legacy_content(
    subject: str,
    *,
    workspace: WorkspaceKey | None = None,
    occurred_at: str = "2026-07-23T08:00:00+00:00",
    timezone_name: str = "UTC",
):
    content = {
        "type": "work_log",
        "occurred_at": occurred_at,
        "timezone": timezone_name,
        "subject": subject,
    }
    if workspace is not None:
        content["metadata"] = {
            "tenant_id": workspace.tenant_id,
            "workspace_id": workspace.workspace_id,
            "namespace": workspace.namespace,
        }
    return content


def _insert_legacy(manager, identifier: str, content: dict):
    with manager.lease("episodic") as conn:
        conn.execute(
            """
            INSERT INTO episodic_memories
            (id,memory_type,content,importance,timestamp,metadata)
            VALUES (?,?,?,?,?,?)
            """,
            (
                identifier,
                "episodic",
                json.dumps(content),
                0.5,
                NOW.isoformat(),
                "{}",
            ),
        )
        conn.commit()


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
async def test_get_scopes_canonical_before_decode(tmp_path, monkeypatch):
    manager, _store, repository = await _repository(tmp_path)
    alpha = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    beta = WorkspaceKey(
        tenant_id="tenant", workspace_id="beta", namespace="ops"
    )
    record = _record("wl_" + "4" * 32, alpha)
    try:
        await repository.create(record)

        def forbidden_decode(*_args, **_kwargs):
            raise AssertionError("foreign canonical content was decoded")

        monkeypatch.setattr(repository, "_decode_canonical", forbidden_decode)
        with pytest.raises(WorkLogWorkspaceMismatchError):
            await repository.get(beta, record.id)
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_get_scopes_inbox_alias_before_projection(tmp_path, monkeypatch):
    manager, _store, repository = await _repository(tmp_path)
    alpha = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    beta = WorkspaceKey(
        tenant_id="tenant", workspace_id="beta", namespace="ops"
    )
    inbox_item_id = "inbox_scoped"
    alias = (
        "inbox_wl_"
        + hashlib.sha256(
            f"inbox_wl|{inbox_item_id}".encode("utf-8")
        ).hexdigest()[:24]
    )
    record = _record("wl_" + "5" * 32, alpha).model_copy(
        update={
            "source": WorkLogSource.INBOX,
            "inbox_item_id": inbox_item_id,
        }
    )
    try:
        await repository.create_from_inbox(record, alias)

        def forbidden_projection(*_args, **_kwargs):
            raise AssertionError("foreign Inbox alias content was projected")

        monkeypatch.setattr(
            repository, "_project_inbox_alias", forbidden_projection
        )
        with pytest.raises(WorkLogWorkspaceMismatchError):
            await repository.get(beta, alias)
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_legacy_lookup_scans_only_visible_workspace(
    tmp_path, monkeypatch
):
    manager, _store, repository = await _repository(tmp_path)
    alpha = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    beta = WorkspaceKey(
        tenant_id="tenant", workspace_id="beta", namespace="ops"
    )
    own_id = "legacy-alpha"
    foreign_id = "legacy-beta"
    _insert_legacy(manager, own_id, _legacy_content("Alpha", workspace=alpha))
    _insert_legacy(manager, foreign_id, _legacy_content("Beta", workspace=beta))
    original = repository._project_row

    def guarded_projection(row):
        if row["id"] == foreign_id:
            raise AssertionError("foreign legacy content was projected")
        return original(row)

    monkeypatch.setattr(repository, "_project_row", guarded_projection)
    own_public_id = "wl_legacy_" + hashlib.sha256(own_id.encode()).hexdigest()
    foreign_public_id = (
        "wl_legacy_" + hashlib.sha256(foreign_id.encode()).hexdigest()
    )
    try:
        assert (await repository.get(alpha, own_public_id)).subject == "Alpha"
        with pytest.raises(WorkLogNotFoundError):
            await repository.get(alpha, foreign_public_id)
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_foreign_malformed_row_does_not_fail_visible_query(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    alpha = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    beta = WorkspaceKey(
        tenant_id="tenant", workspace_id="beta", namespace="ops"
    )
    _insert_legacy(
        manager,
        "foreign-malformed",
        {
            "type": "work_log",
            "metadata": {
                "tenant_id": beta.tenant_id,
                "workspace_id": beta.workspace_id,
                "namespace": beta.namespace,
            },
            "occurred_at": "not-a-date",
        },
    )
    try:
        assert (await repository.list(alpha, WorkLogQuery())).items == ()
        foreign_public_id = (
            "wl_legacy_"
            + hashlib.sha256(b"foreign-malformed").hexdigest()
        )
        with pytest.raises(WorkLogNotFoundError):
            await repository.get(alpha, foreign_public_id)
    finally:
        manager.close_all()


@pytest.mark.asyncio
async def test_default_workspace_legacy_visibility(tmp_path):
    manager, _store, repository = await _repository(tmp_path)
    foreign = WorkspaceKey(
        tenant_id="tenant", workspace_id="alpha", namespace="ops"
    )
    _insert_legacy(manager, "legacy-default", _legacy_content("Default"))
    _insert_legacy(
        manager,
        "legacy-foreign",
        _legacy_content("Foreign", workspace=foreign),
    )
    try:
        page = await repository.list(WorkspaceKey(), WorkLogQuery())
        assert [item.subject for item in page.items] == ["Default"]
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("local_time", "expected_field"),
    [
        ("2026-03-08T02:30:00", "content.occurred_at"),
        ("2026-11-01T01:30:00", "content.occurred_at"),
    ],
)
async def test_dst_nonexistent_and_ambiguous_legacy_times_fail(
    tmp_path, local_time, expected_field
):
    manager, _store, repository = await _repository(tmp_path)
    _insert_legacy(
        manager,
        f"dst-{local_time}",
        _legacy_content(
            "DST",
            occurred_at=local_time,
            timezone_name="America/New_York",
        ),
    )
    try:
        with pytest.raises(WorkLogLegacyProjectionError) as failure:
            await repository.list(WorkspaceKey(), WorkLogQuery())
        assert failure.value.field == expected_field
    finally:
        manager.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("local_time", "expected_utc"),
    [
        ("2026-03-08T01:30:00", "2026-03-08T06:30:00+00:00"),
        ("2026-03-08T03:30:00", "2026-03-08T07:30:00+00:00"),
    ],
)
async def test_dst_valid_legacy_times_project(tmp_path, local_time, expected_utc):
    manager, _store, repository = await _repository(tmp_path)
    _insert_legacy(
        manager,
        f"dst-valid-{local_time}",
        _legacy_content(
            "DST valid",
            occurred_at=local_time,
            timezone_name="America/New_York",
        ),
    )
    try:
        page = await repository.list(WorkspaceKey(), WorkLogQuery())
        assert page.items[0].occurred_at.isoformat() == expected_utc
    finally:
        manager.close_all()

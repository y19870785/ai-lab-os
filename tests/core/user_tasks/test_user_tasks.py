# ruff: noqa: B023, DTZ001, DTZ005, RUF059

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from core.bus.bus import MemoryBus
from core.database import DatabaseManager
from core.errors import ErrorCategory, FailureException
from core.memory.models import MemoryItem, MemoryQuery, MemoryType
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.user_tasks import (
    SQLiteUserTaskRepository,
    UserTask,
    UserTaskPriority,
    UserTaskQuery,
    UserTaskService,
    UserTaskStatus,
)
from core.user_tasks.exceptions import UserTaskPersistenceError
from core.workspace.models import WorkspaceKey

WORKSPACE = WorkspaceKey()


def test_domain_rejects_blank_title_and_naive_datetime():
    with pytest.raises(ValidationError):
        UserTask(title="  ")
    with pytest.raises(ValidationError):
        UserTask(title="task", due_at=datetime.now())
    with pytest.raises(ValidationError):
        UserTask(title="task", timezone="Mars/Olympus_Mons")


def test_domain_normalizes_aware_datetime_and_derives_overdue():
    due = datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)
    task = UserTask(title="task", due_at=due)
    assert task.due_at.utcoffset() == timedelta(0)
    assert task.is_overdue()
    assert not task.model_copy(update={"status": UserTaskStatus.COMPLETED}).is_overdue()


def test_domain_preserves_timezone_for_utc_round_trip():
    local_due = datetime(2026, 7, 16, 15, 30, tzinfo=timezone(timedelta(hours=8)))
    task = UserTask(title="round trip", due_at=local_due, timezone="Asia/Shanghai")
    assert task.due_at == datetime(2026, 7, 16, 7, 30, tzinfo=UTC)
    assert task.due_at_in_timezone().isoformat() == "2026-07-16T15:30:00+08:00"
    query = UserTaskQuery(due_from=local_due, due_to=local_due)
    assert query.due_from == datetime(2026, 7, 16, 7, 30, tzinfo=UTC)
    assert query.due_to == datetime(2026, 7, 16, 7, 30, tzinfo=UTC)


async def _service(path: Path):
    manager = DatabaseManager(path)
    repository = SQLiteUserTaskRepository(manager, path / "tasks.db")
    service = UserTaskService(repository)
    await service.initialize()
    return manager, repository, service


@pytest.mark.asyncio
async def test_crud_filters_transitions_and_idempotency(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    low = await service.create(
        workspace_key=WORKSPACE, title="low", priority=UserTaskPriority.LOW
    )
    high = await service.create(
        workspace_key=WORKSPACE, title="high", priority=UserTaskPriority.HIGH
    )
    assert [
        item.id for item in await service.list(workspace_key=WORKSPACE)
    ] == [high.id, low.id]
    assert len(
        await service.list(
            workspace_key=WORKSPACE,
            query=UserTaskQuery(priority=UserTaskPriority.HIGH),
        )
    ) == 1

    updated = await service.update(
        workspace_key=WORKSPACE, task_id=low.id, title="changed"
    )
    assert updated.title == "changed" and updated.revision == 2
    cleared = await service.update(
        workspace_key=WORKSPACE, task_id=updated.id, due_at=None
    )
    assert cleared.due_at is None
    with pytest.raises(FailureException):
        await service.update(
            workspace_key=WORKSPACE, task_id=cleared.id, title="   "
        )
    completed = await service.complete(
        workspace_key=WORKSPACE, task_id=low.id
    )
    assert completed.status == UserTaskStatus.COMPLETED
    assert (
        await service.complete(workspace_key=WORKSPACE, task_id=low.id)
    ).revision == completed.revision
    with pytest.raises(FailureException) as exc:
        await service.cancel(workspace_key=WORKSPACE, task_id=low.id)
    assert exc.value.failure.category == ErrorCategory.CONFLICT
    reopened = await service.reopen(workspace_key=WORKSPACE, task_id=low.id)
    assert reopened.status == UserTaskStatus.ACTIVE
    await service.close()
    assert manager.health_check("user_tasks")
    manager.close_all()


@pytest.mark.asyncio
async def test_not_found_and_optimistic_concurrency(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    with pytest.raises(FailureException) as exc:
        await service.get(workspace_key=WORKSPACE, task_id="ut_missing")
    assert exc.value.failure.category == ErrorCategory.NOT_FOUND
    task = await service.create(workspace_key=WORKSPACE, title="race")
    await service.update(
        workspace_key=WORKSPACE,
        task_id=task.id,
        title="winner",
        expected_revision=1,
    )
    with pytest.raises(FailureException) as conflict:
        await service.update(
            workspace_key=WORKSPACE,
            task_id=task.id,
            title="stale",
            expected_revision=1,
        )
    assert conflict.value.failure.category == ErrorCategory.CONFLICT
    for invalid_revision in (0, -1):
        with pytest.raises(FailureException) as invalid:
            await service.update(
                workspace_key=WORKSPACE,
                task_id=task.id,
                title="must not overwrite",
                expected_revision=invalid_revision,
            )
        assert invalid.value.failure.category == ErrorCategory.CONFLICT
    assert (
        await service.get(workspace_key=WORKSPACE, task_id=task.id)
    ).title == "winner"
    manager.close_all()


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["complete", "cancel"])
async def test_terminal_transition_checks_caller_revision_before_idempotency(
    tmp_path: Path,
    action: str,
):
    manager, _, service = await _service(tmp_path)
    task = await service.create(workspace_key=WORKSPACE, title=action)
    method = getattr(service, action)

    with pytest.raises(FailureException) as active_stale:
        await method(
            workspace_key=WORKSPACE,
            task_id=task.id,
            expected_revision=task.revision + 1,
        )
    assert active_stale.value.failure.category == ErrorCategory.CONFLICT
    assert (await service.get(
        workspace_key=WORKSPACE,
        task_id=task.id,
    )).revision == task.revision

    terminal = await method(
        workspace_key=WORKSPACE,
        task_id=task.id,
        expected_revision=task.revision,
    )
    with pytest.raises(FailureException) as terminal_stale:
        await method(
            workspace_key=WORKSPACE,
            task_id=task.id,
            expected_revision=task.revision,
        )
    assert terminal_stale.value.failure.category == ErrorCategory.CONFLICT
    unchanged = await service.get(workspace_key=WORKSPACE, task_id=task.id)
    assert unchanged.revision == terminal.revision
    exact = await method(
        workspace_key=WORKSPACE,
        task_id=task.id,
        expected_revision=terminal.revision,
    )
    assert exact.revision == terminal.revision
    manager.close_all()


@pytest.mark.asyncio
async def test_schema_is_idempotent_and_data_survives_restart(tmp_path: Path):
    manager_a, repository_a, service_a = await _service(tmp_path)
    await service_a.initialize()
    task = await service_a.create(
        workspace_key=WORKSPACE, title="persistent"
    )
    await service_a.close()
    manager_a.close_all()

    manager_b, repository_b, service_b = await _service(tmp_path)
    assert (
        await service_b.get(workspace_key=WORKSPACE, task_id=task.id)
    ).title == "persistent"
    completed = await service_b.complete(
        workspace_key=WORKSPACE, task_id=task.id
    )
    assert completed.status == UserTaskStatus.COMPLETED
    manager_b.close_all()


@pytest.mark.asyncio
async def test_manager_owned_connection_is_not_closed_by_repository(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    await repository.close()
    assert manager.health_check("user_tasks")
    with manager.lease("user_tasks") as conn:
        assert conn.execute("SELECT 1").fetchone()[0] == 1
    manager.close_all()


@pytest.mark.asyncio
async def test_repository_rolls_back_sql_and_commit_failures(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    original_lease = manager.lease

    class FailingConnection:
        def __init__(self, connection, *, fail_execute=False, fail_commit=False):
            self._connection = connection
            self.fail_execute = fail_execute
            self.fail_commit = fail_commit
            self.rollback_count = 0

        def execute(self, sql, parameters=()):
            if self.fail_execute and sql.startswith("INSERT"):
                raise sqlite3.OperationalError("injected SQL failure")
            return self._connection.execute(sql, parameters)

        def commit(self):
            if self.fail_commit:
                raise sqlite3.OperationalError("injected commit failure")
            return self._connection.commit()

        def rollback(self):
            self.rollback_count += 1
            return self._connection.rollback()

    @contextmanager
    def failing_lease(*, fail_execute=False, fail_commit=False):
        with original_lease("user_tasks") as connection:
            wrapper = FailingConnection(
                connection, fail_execute=fail_execute, fail_commit=fail_commit
            )
            yield wrapper

    for mode in ("execute", "commit"):
        holder = {}

        @contextmanager
        def lease(name, db_path=None):
            with failing_lease(
                fail_execute=mode == "execute", fail_commit=mode == "commit"
            ) as wrapper:
                holder["connection"] = wrapper
                yield wrapper

        manager.lease = lease
        with pytest.raises(FailureException) as exc:
            await service.create(
                workspace_key=WORKSPACE, title=f"failed-{mode}"
            )
        assert exc.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
        assert holder["connection"].rollback_count == 1
        manager.lease = original_lease
        assert not await service.list(workspace_key=WORKSPACE)

    manager.close_all()


@pytest.mark.asyncio
async def test_failure_events_trace_and_health_lifecycle(tmp_path: Path):
    bus = MemoryBus()
    await bus.start()
    events = []

    async def capture(event):
        events.append(event)

    await bus.subscribe("user_task.failed", capture)
    manager = DatabaseManager(tmp_path)
    repository = SQLiteUserTaskRepository(manager, tmp_path / "tasks.db")
    service = UserTaskService(repository, bus=bus)
    assert (await service.health())["status"] == "not_initialized"
    await service.initialize()
    assert (await service.health())["status"] == "healthy"
    with pytest.raises(FailureException):
        await service.get(
            workspace_key=WORKSPACE,
            task_id="ut_missing",
            trace_id="trace-missing",
        )
    assert events[-1].metadata["trace_id"] == "trace-missing"
    assert events[-1].payload == {"task_id": "ut_missing", "status": "failed"}
    await service.close()
    assert (await service.health())["status"] == "not_initialized"
    await service.close()
    await bus.stop()
    manager.close_all()


@pytest.mark.asyncio
async def test_repository_failure_is_sanitized_as_failure_info(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)

    async def fail_create(task):
        raise UserTaskPersistenceError("private SQL and database path")

    repository.create = fail_create
    with pytest.raises(FailureException) as exc:
        await service.create(
            workspace_key=WORKSPACE,
            title="failure",
            trace_id="trace-store",
        )
    assert exc.value.failure.message == "UserTask create failed"
    assert exc.value.failure.trace_id == "trace-store"
    assert "private" not in exc.value.failure.message
    manager.close_all()


@pytest.mark.asyncio
async def test_metadata_rejects_sensitive_and_non_serializable_values(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    for metadata in (
        {"api_key": "hidden"},
        {"nested": {"token": "hidden"}},
        {"items": [{"password": "hidden"}]},
        {"value": object()},
    ):
        with pytest.raises(FailureException) as exc:
            await service.create(
                workspace_key=WORKSPACE,
                title="invalid",
                metadata=metadata,
            )
        assert exc.value.failure.category == ErrorCategory.VALIDATION
    manager.close_all()


@pytest.mark.asyncio
async def test_legacy_import_is_filtered_non_destructive_and_idempotent(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)

    class LegacyMemory:
        async def retrieve_memory(self, query):
            return [
                SimpleNamespace(id="legacy-task", content={
                    "type": "task", "title": "Imported", "priority": "高",
                    "status": "已完成", "deadline": "2026-07-16",
                    "completed_at": "2026-07-16T10:30:00+08:00",
                }, timestamp=datetime(2026, 7, 15, 9, 0), metadata={
                    "session_id": "legacy-session", "agent_id": "legacy-agent",
                    "source": "ceo_assistant", "timezone": "Asia/Shanghai",
                }),
                SimpleNamespace(id="legacy-cancelled", content={
                    "type": "task", "title": "Cancelled without timestamp",
                    "status": "已取消",
                }, timestamp=datetime(2026, 7, 15, 11, 0), metadata={
                    "timezone": "Asia/Shanghai",
                }),
                SimpleNamespace(id="legacy-decision", content={
                    "type": "decision", "chosen": "Keep original"
                }),
                SimpleNamespace(id="broken", content={"type": "task"}),
                SimpleNamespace(id=None, content={"type": "task", "title": "No ID"}),
                SimpleNamespace(id="bad-shape", content="not-an-object"),
            ]

    first = await service.import_legacy(LegacyMemory())
    second = await service.import_legacy(LegacyMemory())
    assert first.model_dump() == {"imported": 2, "skipped": 1, "failed": 3}
    assert second.imported == 0 and second.skipped == 3 and second.failed == 3
    tasks = await service.list(workspace_key=WORKSPACE)
    assert len(tasks) == 2
    by_legacy_id = {task.legacy_source_id: task for task in tasks}
    imported = by_legacy_id["legacy-task"]
    assert imported.status == UserTaskStatus.COMPLETED
    assert imported.priority == UserTaskPriority.HIGH
    assert imported.due_at_in_timezone().isoformat() == "2026-07-16T23:59:59+08:00"
    assert imported.completed_at.astimezone(
        timezone(timedelta(hours=8))
    ).isoformat() == "2026-07-16T10:30:00+08:00"
    assert imported.session_id == "legacy-session"
    assert imported.agent_id == "legacy-agent"
    assert imported.source == "ceo_assistant"
    cancelled = by_legacy_id["legacy-cancelled"]
    assert cancelled.status == UserTaskStatus.CANCELLED
    assert cancelled.cancelled_at is None
    manager.close_all()


@pytest.mark.asyncio
async def test_legacy_import_pages_beyond_five_hundred(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    items = [
        SimpleNamespace(
            id=f"legacy-{index}",
            content={"type": "task", "title": f"Task {index}"},
            timestamp=datetime(2026, 7, 15, tzinfo=UTC),
            metadata={},
        )
        for index in range(501)
    ]

    class PagedLegacyMemory:
        def __init__(self):
            self.offsets = []

        async def retrieve_memory(self, query):
            self.offsets.append(query.offset)
            return items[query.offset:query.offset + query.top_k]

    memory = PagedLegacyMemory()
    result = await service.import_legacy(memory)
    assert result.model_dump() == {"imported": 501, "skipped": 0, "failed": 0}
    assert memory.offsets == [0, 500]
    assert len(
        await service.list(
            workspace_key=WORKSPACE,
            query=UserTaskQuery(limit=500),
        )
    ) == 500
    manager.close_all()


@pytest.mark.asyncio
async def test_decision_store_honors_offset_for_legacy_pagination(tmp_path: Path):
    store = SQLiteDecisionStore(str(tmp_path / "decision.db"))
    await store.initialize()
    timestamp = datetime(2026, 7, 15, tzinfo=UTC)
    for item_id in ("a", "b", "c"):
        await store.save(MemoryItem(
            id=item_id,
            memory_type=MemoryType.DECISION,
            content={"type": "task", "title": item_id},
            timestamp=timestamp,
        ))
    page = await store.query(MemoryQuery(
        memory_type=MemoryType.DECISION, top_k=1, offset=1
    ))
    assert [item.id for item in page] == ["b"]
    await store.close()


@pytest.mark.asyncio
async def test_corrupt_persisted_rows_are_persistence_failures(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    task_ids = []
    for suffix in ("metadata", "status", "datetime"):
        task_ids.append(
            (
                await service.create(
                    workspace_key=WORKSPACE,
                    title=f"corrupt-{suffix}",
                )
            ).id
        )
    with manager.lease("user_tasks") as conn:
        conn.execute("UPDATE user_tasks SET metadata=? WHERE id=?", ("{broken", task_ids[0]))
        conn.execute("UPDATE user_tasks SET status=? WHERE id=?", ("unknown", task_ids[1]))
        conn.execute("UPDATE user_tasks SET due_at=? WHERE id=?", ("not-a-datetime", task_ids[2]))
        conn.commit()
    for task_id in task_ids:
        with pytest.raises(FailureException) as exc:
            await service.get(workspace_key=WORKSPACE, task_id=task_id)
        assert exc.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
    with pytest.raises(FailureException) as listed:
        await service.list(workspace_key=WORKSPACE)
    assert listed.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
    manager.close_all()

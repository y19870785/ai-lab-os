from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import sqlite3

import pytest
from pydantic import ValidationError

from core.database import DatabaseManager
from core.bus.bus import MemoryBus
from core.errors import ErrorCategory, FailureException
from core.user_tasks.exceptions import UserTaskPersistenceError
from core.user_tasks import (
    SQLiteUserTaskRepository,
    UserTask,
    UserTaskPriority,
    UserTaskQuery,
    UserTaskService,
    UserTaskStatus,
)


def test_domain_rejects_blank_title_and_naive_datetime():
    with pytest.raises(ValidationError):
        UserTask(title="  ")
    with pytest.raises(ValidationError):
        UserTask(title="task", due_at=datetime.now())


def test_domain_normalizes_aware_datetime_and_derives_overdue():
    due = datetime.now(timezone(timedelta(hours=8))) - timedelta(days=1)
    task = UserTask(title="task", due_at=due)
    assert task.due_at.utcoffset() == timedelta(0)
    assert task.is_overdue()
    assert not task.model_copy(update={"status": UserTaskStatus.COMPLETED}).is_overdue()


async def _service(path: Path):
    manager = DatabaseManager(path)
    repository = SQLiteUserTaskRepository(manager, path / "tasks.db")
    service = UserTaskService(repository)
    await service.initialize()
    return manager, repository, service


@pytest.mark.asyncio
async def test_crud_filters_transitions_and_idempotency(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    low = await service.create(title="low", priority=UserTaskPriority.LOW)
    high = await service.create(title="high", priority=UserTaskPriority.HIGH)
    assert [item.id for item in await service.list()] == [high.id, low.id]
    assert len(await service.list(UserTaskQuery(priority=UserTaskPriority.HIGH))) == 1

    updated = await service.update(low.id, title="changed")
    assert updated.title == "changed" and updated.revision == 2
    cleared = await service.update(updated.id, due_at=None)
    assert cleared.due_at is None
    with pytest.raises(FailureException):
        await service.update(cleared.id, title="   ")
    completed = await service.complete(low.id)
    assert completed.status == UserTaskStatus.COMPLETED
    assert (await service.complete(low.id)).revision == completed.revision
    with pytest.raises(FailureException) as exc:
        await service.cancel(low.id)
    assert exc.value.failure.category == ErrorCategory.CONFLICT
    reopened = await service.reopen(low.id)
    assert reopened.status == UserTaskStatus.ACTIVE
    await service.close()
    assert manager.health_check("user_tasks")
    manager.close_all()


@pytest.mark.asyncio
async def test_not_found_and_optimistic_concurrency(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    with pytest.raises(FailureException) as exc:
        await service.get("ut_missing")
    assert exc.value.failure.category == ErrorCategory.NOT_FOUND
    task = await service.create(title="race")
    await service.update(task.id, title="winner", expected_revision=1)
    with pytest.raises(FailureException) as conflict:
        await service.update(task.id, title="stale", expected_revision=1)
    assert conflict.value.failure.category == ErrorCategory.CONFLICT
    manager.close_all()


@pytest.mark.asyncio
async def test_schema_is_idempotent_and_data_survives_restart(tmp_path: Path):
    manager_a, repository_a, service_a = await _service(tmp_path)
    await service_a.initialize()
    task = await service_a.create(title="persistent")
    await service_a.close()
    manager_a.close_all()

    manager_b, repository_b, service_b = await _service(tmp_path)
    assert (await service_b.get(task.id)).title == "persistent"
    completed = await service_b.complete(task.id)
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
            await service.create(title=f"failed-{mode}")
        assert exc.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
        assert holder["connection"].rollback_count == 1
        manager.lease = original_lease
        assert not await service.list()

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
        await service.get("ut_missing", trace_id="trace-missing")
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
        await service.create(title="failure", trace_id="trace-store")
    assert exc.value.failure.message == "UserTask create failed"
    assert exc.value.failure.trace_id == "trace-store"
    assert "private" not in exc.value.failure.message
    manager.close_all()


@pytest.mark.asyncio
async def test_metadata_rejects_sensitive_and_non_serializable_values(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)
    for metadata in ({"api_key": "hidden"}, {"value": object()}):
        with pytest.raises(FailureException) as exc:
            await service.create(title="invalid", metadata=metadata)
        assert exc.value.failure.category == ErrorCategory.VALIDATION
    manager.close_all()


@pytest.mark.asyncio
async def test_legacy_import_is_filtered_non_destructive_and_idempotent(tmp_path: Path):
    manager, repository, service = await _service(tmp_path)

    class LegacyMemory:
        async def retrieve_memory(self, query):
            return [
                SimpleNamespace(id="legacy-task", content={
                    "type": "task", "title": "Imported", "priority": "高"
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
    assert first.model_dump() == {"imported": 1, "skipped": 1, "failed": 3}
    assert second.imported == 0 and second.skipped == 2 and second.failed == 3
    tasks = await service.list()
    assert len(tasks) == 1 and tasks[0].legacy_source_id == "legacy-task"
    manager.close_all()

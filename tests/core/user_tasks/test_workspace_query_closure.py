from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.database import DatabaseManager
from core.errors import ErrorCategory, FailureException
from core.user_tasks import (
    SQLiteUserTaskRepository,
    UserTask,
    UserTaskPriority,
    UserTaskQuery,
    UserTaskService,
    UserTaskStatus,
)
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock

AS_OF = datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
DEFAULT = WorkspaceKey()
TENANT_B = WorkspaceKey(
    tenant_id="tenant-b",
    workspace_id="workspace-1",
    namespace="namespace-x",
)
WORKSPACE_2 = WorkspaceKey(
    tenant_id="tenant-a",
    workspace_id="workspace-2",
    namespace="namespace-x",
)
NAMESPACE_Y = WorkspaceKey(
    tenant_id="tenant-a",
    workspace_id="workspace-1",
    namespace="namespace-y",
)
LOCAL = WorkspaceKey(
    tenant_id="tenant-a",
    workspace_id="workspace-1",
    namespace="namespace-x",
)


async def _stack(path: Path):
    manager = DatabaseManager(path)
    repository = SQLiteUserTaskRepository(manager, path / "tasks.db")
    clock = MutableClock(AS_OF)
    service = UserTaskService(repository, clock=clock)
    await service.initialize()
    return manager, repository, service, clock


async def _assert_not_found(awaitable) -> None:
    with pytest.raises(FailureException) as exc:
        await awaitable
    assert exc.value.failure.category == ErrorCategory.NOT_FOUND
    assert "workspace" not in exc.value.failure.message.casefold()


@pytest.mark.asyncio
async def test_workspace_triple_isolation_and_filter_before_limit(
    tmp_path: Path,
) -> None:
    manager, _, service, _ = await _stack(tmp_path)
    workspaces = (LOCAL, TENANT_B, WORKSPACE_2, NAMESPACE_Y, DEFAULT)
    created = {}
    for index, workspace_key in enumerate(workspaces):
        created[workspace_key.model_dump_json()] = await service.create(
            workspace_key=workspace_key,
            title=f"Task {index}",
            priority=UserTaskPriority.LOW,
            due_at=AS_OF + timedelta(days=1),
            metadata={
                "business": index,
                "workspace": {
                    "tenant_id": "attacker",
                    "workspace_id": "attacker",
                    "namespace": "attacker",
                },
            },
        )

    for workspace_key in workspaces:
        visible = await service.list(workspace_key=workspace_key)
        assert [task.id for task in visible] == [
            created[workspace_key.model_dump_json()].id
        ]

    local = created[LOCAL.model_dump_json()]
    assert local.metadata["workspace"] == {
        "tenant_id": "tenant-a",
        "workspace_id": "workspace-1",
        "namespace": "namespace-x",
    }
    for index in range(3):
        await service.create(
            workspace_key=TENANT_B,
            title=f"Foreign urgent {index}",
            priority=UserTaskPriority.URGENT,
            due_at=AS_OF - timedelta(days=index + 1),
        )
    page = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(limit=1),
    )
    assert [task.id for task in page] == [local.id]
    manager.close_all()


@pytest.mark.asyncio
async def test_cross_workspace_id_and_mutations_are_not_found_and_unchanged(
    tmp_path: Path,
) -> None:
    manager, _, service, _ = await _stack(tmp_path)
    active = {}
    for operation in ("get", "update", "complete", "cancel"):
        active[operation] = await service.create(
            workspace_key=LOCAL,
            title=operation,
            metadata={"operation": operation},
        )
    terminal = await service.create(
        workspace_key=LOCAL,
        title="reopen",
        status=UserTaskStatus.COMPLETED,
        completed_at=AS_OF - timedelta(hours=1),
        metadata={"operation": "reopen"},
    )
    before = {
        task.id: task.model_dump(mode="json")
        for task in (*active.values(), terminal)
    }

    await _assert_not_found(
        service.get(workspace_key=TENANT_B, task_id=active["get"].id)
    )
    await _assert_not_found(
        service.update(
            workspace_key=TENANT_B,
            task_id=active["update"].id,
            title="leak",
        )
    )
    await _assert_not_found(
        service.complete(
            workspace_key=TENANT_B,
            task_id=active["complete"].id,
        )
    )
    await _assert_not_found(
        service.cancel(
            workspace_key=TENANT_B,
            task_id=active["cancel"].id,
        )
    )
    await _assert_not_found(
        service.reopen(workspace_key=TENANT_B, task_id=terminal.id)
    )

    for task_id, snapshot in before.items():
        current = await service.get(workspace_key=LOCAL, task_id=task_id)
        assert current.model_dump(mode="json") == snapshot
    manager.close_all()


@pytest.mark.asyncio
async def test_legacy_incomplete_workspace_is_default_read_only(
    tmp_path: Path,
) -> None:
    manager, repository, service, _ = await _stack(tmp_path)
    legacy_metadata = (
        {},
        {"workspace": {}},
        {"workspace": {"workspace_id": "alpha"}},
        {
            "workspace": {
                "tenant_id": "tenant",
                "workspace_id": "alpha",
            }
        },
        {
            "workspace": {
                "tenant_id": "",
                "workspace_id": "",
                "namespace": "",
            }
        },
    )
    for index, metadata in enumerate(legacy_metadata):
        await repository.create(
            UserTask(
                id=f"ut_legacy_{index}",
                title=f"Legacy {index}",
                metadata=metadata,
                created_at=AS_OF,
                updated_at=AS_OF,
            )
        )
    with manager.lease("user_tasks") as conn:
        before = [
            tuple(row)
            for row in conn.execute(
                "SELECT id, metadata, revision FROM user_tasks ORDER BY id"
            ).fetchall()
        ]

    default_tasks = await service.list(workspace_key=DEFAULT)
    assert {task.id for task in default_tasks} == {
        f"ut_legacy_{index}" for index in range(len(legacy_metadata))
    }
    assert await service.list(workspace_key=LOCAL) == []

    with manager.lease("user_tasks") as conn:
        after = [
            tuple(row)
            for row in conn.execute(
                "SELECT id, metadata, revision FROM user_tasks ORDER BY id"
            ).fetchall()
        ]
    assert after == before

    with manager.lease("user_tasks") as conn:
        conn.execute(
            "UPDATE user_tasks SET metadata = ? WHERE id = ?",
            ("{broken", "ut_legacy_0"),
        )
        conn.commit()
    with pytest.raises(FailureException) as malformed:
        await service.list(workspace_key=DEFAULT)
    assert malformed.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
    manager.close_all()


@pytest.mark.asyncio
async def test_malformed_metadata_respects_workspace_visibility_before_failure(
    tmp_path: Path,
) -> None:
    manager, _, service, _ = await _stack(tmp_path)
    local = await service.create(
        workspace_key=LOCAL,
        title="Visible local task",
    )
    corrupted = await service.create(
        workspace_key=TENANT_B,
        title="Corrupted foreign task",
    )
    with manager.lease("user_tasks") as conn:
        conn.execute(
            "UPDATE user_tasks SET metadata = ? WHERE id = ?",
            ("{broken", corrupted.id),
        )
        conn.commit()
        before = tuple(
            conn.execute(
                """
                SELECT revision, status, updated_at, completed_at, cancelled_at,
                       metadata
                FROM user_tasks
                WHERE id = ?
                """,
                (corrupted.id,),
            ).fetchone()
        )

    visible = await service.list(workspace_key=LOCAL)
    assert [task.id for task in visible] == [local.id]
    assert await service.list(workspace_key=TENANT_B) == []

    await _assert_not_found(
        service.get(workspace_key=LOCAL, task_id=corrupted.id)
    )
    await _assert_not_found(
        service.update(
            workspace_key=LOCAL,
            task_id=corrupted.id,
            title="must not change",
        )
    )
    await _assert_not_found(
        service.complete(workspace_key=LOCAL, task_id=corrupted.id)
    )
    await _assert_not_found(
        service.cancel(workspace_key=LOCAL, task_id=corrupted.id)
    )
    await _assert_not_found(
        service.reopen(workspace_key=LOCAL, task_id=corrupted.id)
    )

    with pytest.raises(FailureException) as malformed:
        await service.list(workspace_key=DEFAULT)
    assert malformed.value.failure.category == ErrorCategory.PERSISTENCE_FAILURE
    assert "{broken" not in malformed.value.failure.message
    assert "metadata" not in malformed.value.failure.message.casefold()

    with manager.lease("user_tasks") as conn:
        after = tuple(
            conn.execute(
                """
                SELECT revision, status, updated_at, completed_at, cancelled_at,
                       metadata
                FROM user_tasks
                WHERE id = ?
                """,
                (corrupted.id,),
            ).fetchone()
        )
    assert after == before
    manager.close_all()


@pytest.mark.asyncio
async def test_terminal_ranges_are_utc_half_open(tmp_path: Path) -> None:
    manager, _, service, _ = await _stack(tmp_path)
    start = AS_OF - timedelta(hours=2)
    end = AS_OF
    completed_ids = []
    cancelled_ids = []
    for index, instant in enumerate(
        (start, start + timedelta(hours=1), end)
    ):
        completed_ids.append(
            (
                await service.create(
                    workspace_key=LOCAL,
                    title=f"Completed {index}",
                    status=UserTaskStatus.COMPLETED,
                    completed_at=instant,
                )
            ).id
        )
        cancelled_ids.append(
            (
                await service.create(
                    workspace_key=LOCAL,
                    title=f"Cancelled {index}",
                    status=UserTaskStatus.CANCELLED,
                    cancelled_at=instant,
                )
            ).id
        )
    await service.create(
        workspace_key=LOCAL,
        title="Completed without timestamp",
        status=UserTaskStatus.COMPLETED,
    )

    completed = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(completed_from=start, completed_to=end),
    )
    cancelled = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(cancelled_from=start, cancelled_to=end),
    )
    assert {task.id for task in completed} == set(completed_ids[:2])
    assert {task.id for task in cancelled} == set(cancelled_ids[:2])
    manager.close_all()


@pytest.mark.asyncio
async def test_overdue_uses_resolved_as_of_and_frozen_clock(
    tmp_path: Path,
) -> None:
    manager, repository, service, clock = await _stack(tmp_path)
    past = await service.create(
        workspace_key=LOCAL,
        title="Past",
        due_at=AS_OF - timedelta(seconds=1),
    )
    equal = await service.create(
        workspace_key=LOCAL,
        title="Equal",
        due_at=AS_OF,
    )
    future = await service.create(
        workspace_key=LOCAL,
        title="Future",
        due_at=AS_OF + timedelta(seconds=1),
    )
    completed = await service.create(
        workspace_key=LOCAL,
        title="Completed",
        due_at=AS_OF - timedelta(days=1),
        status=UserTaskStatus.COMPLETED,
        completed_at=AS_OF,
    )
    cancelled = await service.create(
        workspace_key=LOCAL,
        title="Cancelled",
        due_at=AS_OF - timedelta(days=1),
        status=UserTaskStatus.CANCELLED,
        cancelled_at=AS_OF,
    )

    overdue = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(overdue=True),
        as_of=AS_OF,
    )
    assert [task.id for task in overdue] == [past.id]
    not_overdue = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(overdue=False),
        as_of=AS_OF,
    )
    assert {task.id for task in not_overdue} == {equal.id, future.id}
    assert completed.id not in {task.id for task in overdue}
    assert cancelled.id not in {task.id for task in overdue}

    clock.current = AS_OF + timedelta(days=30)
    same = await service.list(
        workspace_key=LOCAL,
        query=UserTaskQuery(overdue=True),
        as_of=AS_OF,
    )
    assert [task.id for task in same] == [past.id]
    assert "utc_now" not in inspect.getsource(repository.list)
    manager.close_all()


@pytest.mark.asyncio
async def test_stable_workspace_pagination_has_no_gaps_or_foreign_consumption(
    tmp_path: Path,
) -> None:
    manager, _, service, _ = await _stack(tmp_path)
    local_ids = []
    for index in range(13):
        local_ids.append(
            (
                await service.create(
                    workspace_key=LOCAL,
                    title=f"Local {index}",
                    priority=UserTaskPriority(
                        ("urgent", "high", "medium", "low")[index % 4]
                    ),
                    due_at=AS_OF + timedelta(minutes=index % 3),
                )
            ).id
        )
        await service.create(
            workspace_key=TENANT_B,
            title=f"Foreign {index}",
            priority=UserTaskPriority.URGENT,
            due_at=AS_OF - timedelta(days=index + 1),
        )

    pages = []
    for offset in (0, 5, 10):
        pages.extend(
            await service.list(
                workspace_key=LOCAL,
                query=UserTaskQuery(limit=5, offset=offset),
            )
        )
    assert len({task.id for task in pages}) == len(local_ids)
    assert {task.id for task in pages} == set(local_ids)
    assert (
        await service.list(
            workspace_key=LOCAL,
            query=UserTaskQuery(limit=5, offset=100),
        )
        == []
    )
    manager.close_all()


@pytest.mark.asyncio
async def test_query_validation_precedes_repository_access() -> None:
    class TrackingRepository:
        list_called = False

        async def list(self, *_args, **_kwargs):
            self.list_called = True
            return []

    repository = TrackingRepository()
    service = UserTaskService(repository, clock=MutableClock(AS_OF))
    with pytest.raises(FailureException) as invalid_range:
        await service.list(
            workspace_key=LOCAL,
            completed_from=AS_OF,
            completed_to=AS_OF,
        )
    assert invalid_range.value.failure.category == ErrorCategory.VALIDATION
    assert not repository.list_called

    with pytest.raises(FailureException) as naive_as_of:
        await service.list(
            workspace_key=LOCAL,
            overdue=True,
            as_of=datetime(2026, 7, 27, 8, 0),  # noqa: DTZ001 - rejection case
        )
    assert naive_as_of.value.failure.category == ErrorCategory.VALIDATION
    assert not repository.list_called

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.database import DatabaseManager
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.inbox import (
    InboxResolutionClaimState,
    InboxResolvedType,
    InboxService,
    InboxStatus,
    SQLiteInboxRepository,
)
from core.inbox.exceptions import (
    InboxRepositoryError,
    InboxResolutionClaimNotFoundError,
)
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


class FakeUserTasks:
    def __init__(self):
        self.tasks = {}
        self.create_attempts = 0

    async def create(self, **values):
        self.create_attempts += 1
        await asyncio.sleep(0)
        task_id = values["task_id"]
        if task_id in self.tasks:
            raise FailureException(FailureInfo(
                code="user_tasks.create.conflict",
                category=ErrorCategory.CONFLICT,
                message="UserTask already exists",
                component="user_tasks",
                operation="create",
            ))
        task = SimpleNamespace(id=task_id, metadata=values["metadata"])
        self.tasks[task_id] = task
        return task

    async def get(self, task_id, _trace_id=""):
        return self.tasks[task_id]


class BlockingUserTasks(FakeUserTasks):
    def __init__(self):
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def create(self, **values):
        self.create_attempts += 1
        self.started.set()
        await self.release.wait()
        task_id = values["task_id"]
        task = SimpleNamespace(id=task_id, metadata=values["metadata"])
        self.tasks[task_id] = task
        return task


class FakeReminderOrchestrator:
    def __init__(self):
        self.calls = 0
        self.reminders = {}

    async def create_for_task(self, **values):
        self.calls += 1
        reminder_id = f"rem_{values['idempotency_key'].split(':')[1]}"
        self.reminders.setdefault(reminder_id, values)
        return SimpleNamespace(reminder_id=reminder_id)


async def _services(tmp_path, *, user_tasks=None, reminder=None):
    database_path = tmp_path / "inbox.db"
    repository_a = SQLiteInboxRepository(DatabaseManager(tmp_path / "a"), database_path)
    repository_b = SQLiteInboxRepository(DatabaseManager(tmp_path / "b"), database_path)
    await repository_a.initialize()
    await repository_b.initialize()
    clock = MutableClock(NOW)
    dependencies = {
        "clock": clock,
        "user_tasks": user_tasks,
        "reminder_orchestrator": reminder,
        "timezone_name": "Asia/Shanghai",
    }
    return (
        InboxService(repository_a, **dependencies),
        InboxService(repository_b, **dependencies),
        repository_a,
        repository_b,
    )


@pytest.mark.asyncio
async def test_cross_service_different_type_race_creates_only_claim_winner(tmp_path):
    user_tasks = BlockingUserTasks()
    reminders = FakeReminderOrchestrator()
    service_a, service_b, _, _ = await _services(
        tmp_path, user_tasks=user_tasks, reminder=reminders
    )
    workspace = WorkspaceKey()
    item = await service_a.capture(
        workspace_key=workspace, content="竞争解析", source="api"
    )

    task_resolution = asyncio.create_task(service_a.resolve_to_task(
        workspace_key=workspace, inbox_item_id=item.id, title="唯一任务"
    ))
    await user_tasks.started.wait()
    with pytest.raises(FailureException) as loser:
        await service_b.resolve_to_reminder(
            workspace_key=workspace,
            inbox_item_id=item.id,
            title="不应创建的提醒",
            scheduled_at=NOW + timedelta(hours=1),
        )
    user_tasks.release.set()
    winner = await task_resolution

    stored = await service_b.get(workspace_key=workspace, inbox_item_id=item.id)
    assert loser.value.failure.code == "inbox.already_resolved"
    assert loser.value.failure.details == {
        "claimed_type": "user_task",
        "target_id": winner.resolved_target_id,
        "claim_state": "claimed",
        "resolved_type": "user_task",
        "resolved_target_id": winner.resolved_target_id,
    }
    assert len(user_tasks.tasks) == 1
    assert reminders.calls == 0
    assert stored.resolved_type == InboxResolvedType.USER_TASK
    assert stored.resolved_target_id in user_tasks.tasks


@pytest.mark.asyncio
async def test_cross_service_same_type_retry_creates_at_most_one_target(tmp_path):
    user_tasks = FakeUserTasks()
    service_a, service_b, _, _ = await _services(tmp_path, user_tasks=user_tasks)
    workspace = WorkspaceKey()
    item = await service_a.capture(
        workspace_key=workspace, content="同类型竞争", source="api"
    )

    results = await asyncio.gather(
        service_a.resolve_to_task(
            workspace_key=workspace, inbox_item_id=item.id, title="同一个任务"
        ),
        service_b.resolve_to_task(
            workspace_key=workspace, inbox_item_id=item.id, title="同一个任务"
        ),
        return_exceptions=True,
    )

    failures = [result for result in results if isinstance(result, FailureException)]
    assert all(failure.failure.code == "inbox.already_resolved" for failure in failures)
    stored = await service_a.get(workspace_key=workspace, inbox_item_id=item.id)
    assert stored.status == InboxStatus.RESOLVED
    assert stored.resolved_type == InboxResolvedType.USER_TASK
    assert set(user_tasks.tasks) == {stored.resolved_target_id}


@pytest.mark.asyncio
async def test_target_created_crash_recovers_without_duplicate(tmp_path, monkeypatch):
    user_tasks = FakeUserTasks()
    service_a, service_b, repository_a, repository_b = await _services(
        tmp_path, user_tasks=user_tasks
    )
    workspace = WorkspaceKey()
    item = await service_a.capture(
        workspace_key=workspace, content="目标后崩溃", source="api"
    )

    async def fail_completion(*_args, **_kwargs):
        raise InboxRepositoryError("injected completion crash")

    monkeypatch.setattr(repository_a, "complete_resolution", fail_completion)
    with pytest.raises(FailureException) as interrupted:
        await service_a.resolve_to_task(
            workspace_key=workspace, inbox_item_id=item.id, title="可恢复任务"
        )
    claim_before = await repository_b.get_resolution_claim(workspace, item.id)
    pending = await service_b.get(workspace_key=workspace, inbox_item_id=item.id)

    recovered = await service_b.resolve_to_task(
        workspace_key=workspace, inbox_item_id=item.id, title="可恢复任务"
    )
    claim_after = await repository_b.get_resolution_claim(workspace, item.id)

    assert interrupted.value.failure.code == "inbox.resolve_failed"
    assert claim_before.state == InboxResolutionClaimState.TARGET_CREATED
    assert pending.status == InboxStatus.PENDING
    assert recovered.status == InboxStatus.RESOLVED
    assert claim_after.state == InboxResolutionClaimState.COMPLETED
    assert user_tasks.create_attempts == 1
    assert set(user_tasks.tasks) == {recovered.resolved_target_id}


@pytest.mark.asyncio
async def test_claimed_before_target_crash_recovers_in_new_service(tmp_path):
    user_tasks = FakeUserTasks()
    _, service_b, repository_a, repository_b = await _services(
        tmp_path, user_tasks=user_tasks
    )
    workspace = WorkspaceKey()
    item = await service_b.capture(
        workspace_key=workspace, content="目标前崩溃", source="api"
    )
    target_id = service_b._target_id("ut_inbox", item.id)
    await repository_a.claim_resolution(
        workspace,
        item.id,
        resolved_type=InboxResolvedType.USER_TASK,
        target_key=target_id,
        target_id=target_id,
        now=NOW,
    )

    recovered = await service_b.resolve_to_task(
        workspace_key=workspace, inbox_item_id=item.id, title="恢复创建任务"
    )
    claim = await repository_b.get_resolution_claim(workspace, item.id)

    assert recovered.resolved_target_id == target_id
    assert claim.state == InboxResolutionClaimState.COMPLETED
    assert set(user_tasks.tasks) == {target_id}


@pytest.mark.asyncio
async def test_wrong_workspace_cannot_claim_or_create_target(tmp_path):
    user_tasks = FakeUserTasks()
    service_a, service_b, _, repository_b = await _services(
        tmp_path, user_tasks=user_tasks
    )
    alpha = WorkspaceKey(workspace_id="alpha")
    item = await service_a.capture(
        workspace_key=alpha, content="workspace protected", source="api"
    )

    with pytest.raises(FailureException) as mismatch:
        await service_b.resolve_to_task(
            workspace_key=WorkspaceKey(workspace_id="beta"),
            inbox_item_id=item.id,
            title="禁止创建",
        )

    assert mismatch.value.failure.code == "inbox.workspace_mismatch"
    assert user_tasks.tasks == {}
    with pytest.raises(InboxResolutionClaimNotFoundError):
        await repository_b.get_resolution_claim(alpha, item.id)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("claimed_type", "loser_operation"),
    [
        (InboxResolvedType.NOTE, "task"),
        (InboxResolvedType.DISMISSED, "task"),
        (InboxResolvedType.DISMISSED, "note"),
    ],
)
async def test_note_and_dismiss_claims_exclude_other_resolutions(
    tmp_path, claimed_type, loser_operation
):
    user_tasks = FakeUserTasks()
    service_a, service_b, repository_a, repository_b = await _services(
        tmp_path, user_tasks=user_tasks
    )
    workspace = WorkspaceKey()
    item = await service_a.capture(
        workspace_key=workspace, content="内部状态竞争", source="api"
    )
    await repository_a.claim_resolution(
        workspace,
        item.id,
        resolved_type=claimed_type,
        target_key=None,
        target_id=None,
        now=NOW,
    )

    with pytest.raises(FailureException) as loser:
        if loser_operation == "task":
            await service_b.resolve_to_task(
                workspace_key=workspace, inbox_item_id=item.id, title="禁止创建"
            )
        else:
            await service_b.resolve_as_note(
                workspace_key=workspace, inbox_item_id=item.id
            )
    result = (
        await service_a.resolve_as_note(
            workspace_key=workspace, inbox_item_id=item.id
        )
        if claimed_type == InboxResolvedType.NOTE
        else await service_a.dismiss(
            workspace_key=workspace, inbox_item_id=item.id
        )
    )
    claim = await repository_b.get_resolution_claim(workspace, item.id)

    assert loser.value.failure.code == "inbox.already_resolved"
    assert user_tasks.tasks == {}
    assert result.resolved_type == claimed_type
    assert claim.state == InboxResolutionClaimState.COMPLETED

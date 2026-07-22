from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from core.bus.bus import MemoryBus
from core.database import DatabaseManager
from core.errors import ErrorCategory, FailureException, RuntimeStatus
from core.waiting_for import SQLiteWaitingForRepository, WaitingForService
from core.workspace.models import WorkspaceKey


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


async def _service(path: Path, *, bus=None):
    manager = DatabaseManager(path)
    repository = SQLiteWaitingForRepository(manager, path / "followups.db")
    clock = MutableClock(datetime(2026, 7, 22, 8, tzinfo=timezone.utc))
    service = WaitingForService(repository, bus=bus, clock=clock)
    await service.initialize()
    return manager, service, clock


@pytest.mark.asyncio
async def test_service_lifecycle_and_append_only_history(tmp_path: Path):
    manager, service, clock = await _service(tmp_path)
    workspace = WorkspaceKey(tenant_id="tenant-a", workspace_id="workspace-a")
    created = await service.create(
        workspace_key=workspace,
        subject="Supplier reply",
        waiting_on="Packaging supplier",
        next_review_at=clock.now() + timedelta(days=1),
        source="test",
    )
    followed = await service.record_follow_up(
        workspace_key=workspace,
        waiting_for_id=created.item.id,
        expected_revision=1,
        note="Sent a reminder",
        source="test",
    )
    snoozed = await service.snooze(
        workspace_key=workspace,
        waiting_for_id=created.item.id,
        expected_revision=followed.item.revision,
        next_review_at=clock.now() + timedelta(days=2),
        source="test",
    )
    resolved = await service.resolve(
        workspace_key=workspace,
        waiting_for_id=created.item.id,
        expected_revision=snoozed.item.revision,
        resolution_note="Supplier confirmed",
        source="test",
    )
    reopened = await service.reopen(
        workspace_key=workspace,
        waiting_for_id=created.item.id,
        expected_revision=resolved.item.revision,
        note="Need one more confirmation",
        source="test",
    )
    cancelled = await service.cancel(
        workspace_key=workspace,
        waiting_for_id=created.item.id,
        expected_revision=reopened.item.revision,
        note="No longer required",
        source="test",
    )

    assert cancelled.item.revision == 6
    history = await service.list_events(
        workspace_key=workspace, waiting_for_id=created.item.id
    )
    assert [event.event_type.value for event in history.items] == [
        "created",
        "followed_up",
        "snoozed",
        "resolved",
        "reopened",
        "cancelled",
    ]
    await service.close()
    manager.close_all()


@pytest.mark.asyncio
async def test_service_maps_conflicts_and_workspace_mismatch_safely(tmp_path: Path):
    manager, service, _ = await _service(tmp_path)
    owner = WorkspaceKey(tenant_id="tenant-a", workspace_id="workspace-a")
    stranger = WorkspaceKey(tenant_id="tenant-b", workspace_id="workspace-b")
    created = await service.create(
        workspace_key=owner,
        subject="Private acquisition",
        waiting_on="Legal counsel",
        source="test",
    )

    with pytest.raises(FailureException) as hidden:
        await service.get(workspace_key=stranger, waiting_for_id=created.item.id)
    assert hidden.value.failure.category == ErrorCategory.NOT_FOUND
    assert "Private acquisition" not in str(hidden.value.failure)

    await service.resolve(
        workspace_key=owner,
        waiting_for_id=created.item.id,
        expected_revision=1,
        resolution_note="Done",
        source="test",
    )
    with pytest.raises(FailureException) as stale:
        await service.cancel(
            workspace_key=owner,
            waiting_for_id=created.item.id,
            expected_revision=1,
            note="Stale writer",
            source="test",
        )
    assert stale.value.failure.category == ErrorCategory.CONFLICT
    history = await service.list_events(
        workspace_key=owner, waiting_for_id=created.item.id
    )
    assert len(history.items) == 2
    manager.close_all()


@pytest.mark.asyncio
async def test_event_publication_is_safe_and_post_commit_failure_degrades_health(
    tmp_path: Path,
):
    bus = MemoryBus()
    received = []
    await bus.subscribe("waiting_for.created", received.append)
    await bus.start()
    manager, service, _ = await _service(tmp_path, bus=bus)
    workspace = WorkspaceKey(workspace_id="workspace-a", trace_id="trace-1")
    created = await service.create(
        workspace_key=workspace,
        subject="Vendor confirmation",
        waiting_on="Vendor",
        metadata={"public": "safe"},
        source="test",
    )
    assert received[0].payload == {
        "waiting_for_id": created.item.id,
        "event_id": created.event.id,
        "event_type": "created",
        "status": "open",
        "revision": 1,
    }
    assert "subject" not in received[0].payload

    async def fail_publish(_event):
        raise RuntimeError("event sink unavailable")

    bus.add_before_publish_hook(fail_publish)
    persisted = await service.create(
        workspace_key=workspace,
        subject="Persist despite bus failure",
        waiting_on="Vendor",
        source="test",
    )
    assert (await service.get(
        workspace_key=workspace, waiting_for_id=persisted.item.id
    )).subject == "Persist despite bus failure"
    assert (await service.health())["status"] == RuntimeStatus.DEGRADED.value
    await bus.stop()
    manager.close_all()

from datetime import datetime, timedelta, timezone

import pytest

from core.database import DatabaseManager
from core.inbox import (
    InboxItem,
    InboxResolvedType,
    InboxStatus,
    SQLiteInboxRepository,
)
from core.inbox.exceptions import InboxWorkspaceMismatchError
from core.workspace.models import WorkspaceKey


BASE_TIME = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


def _item(workspace, item_id, minute=0):
    now = BASE_TIME + timedelta(minutes=minute)
    return InboxItem(
        id=item_id,
        workspace_key=workspace,
        content=f"capture {item_id}",
        source="api",
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_crud_workspace_filter_sort_and_pagination(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInboxRepository(manager, tmp_path / "inbox.db")
    await repository.initialize()
    alpha = WorkspaceKey(workspace_id="alpha")
    beta = WorkspaceKey(workspace_id="beta")

    await repository.save(_item(alpha, "inbox_a", 0))
    await repository.save(_item(alpha, "inbox_b", 1))
    await repository.save(_item(alpha, "inbox_c", 1))
    await repository.save(_item(beta, "inbox_other", 2))

    page = await repository.list(alpha, limit=2)
    assert [item.id for item in page.items] == ["inbox_c", "inbox_b"]
    assert page.has_more is True
    second = await repository.list(alpha, limit=2, offset=2)
    assert [item.id for item in second.items] == ["inbox_a"]
    with pytest.raises(InboxWorkspaceMismatchError):
        await repository.get(alpha, "inbox_other")


@pytest.mark.asyncio
async def test_resolved_status_persists_across_manager_restart(tmp_path):
    path = tmp_path / "inbox.db"
    workspace = WorkspaceKey(workspace_id="alpha")
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInboxRepository(manager, path)
    await repository.initialize()
    pending = await repository.save(_item(workspace, "inbox_resolve"))
    resolved = pending.model_copy(
        update={
            "status": InboxStatus.RESOLVED,
            "resolved_at": BASE_TIME,
            "resolved_type": InboxResolvedType.USER_TASK,
            "resolved_target_id": "ut_123",
        }
    )
    resolved = InboxItem.model_validate(resolved.model_dump())
    saved = await repository.resolve(resolved, expected_revision=1)
    assert saved.revision == 2
    manager.close_all()

    restarted_manager = DatabaseManager(tmp_path)
    restarted = SQLiteInboxRepository(restarted_manager, path)
    await restarted.initialize()
    found = await restarted.get(workspace, "inbox_resolve")
    assert found.status == InboxStatus.RESOLVED
    assert found.resolved_target_id == "ut_123"


@pytest.mark.asyncio
async def test_repository_close_does_not_close_borrowed_connection(tmp_path):
    manager = DatabaseManager(tmp_path)
    repository = SQLiteInboxRepository(manager, tmp_path / "inbox.db")
    await repository.initialize()
    borrowed = manager.get_connection("inbox")

    await repository.close()

    assert borrowed.execute("SELECT 1").fetchone()[0] == 1

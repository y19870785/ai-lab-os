from datetime import datetime, timedelta, timezone

import pytest

from core.errors import FailureException
from core.inbox import InboxResolvedType, InboxStatus
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


NOW = datetime(2026, 7, 19, 4, 0, tzinfo=timezone.utc)


async def _system(tmp_path):
    system = await create_system(
        make_test_settings(
            tmp_path,
            enable_scheduler=True,
            enable_reminders=True,
            timezone_name="Asia/Shanghai",
            scheduler_tick_interval=0.01,
        ),
        clock=MutableClock(NOW),
    )
    await system.start()
    return system


@pytest.mark.asyncio
async def test_capture_list_get_note_and_dismiss(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        first = await system.inbox_service.capture(
            workspace_key=workspace,
            content=" 一个想法 ",
            source="api",
            metadata={"channel": "test"},
        )
        second = await system.inbox_service.capture(
            workspace_key=workspace, content="无价值记录", source="cli"
        )
        assert (await system.inbox_service.get(
            workspace_key=workspace, inbox_item_id=first.id
        )).content == "一个想法"

        note = await system.inbox_service.resolve_as_note(
            workspace_key=workspace, inbox_item_id=first.id
        )
        dismissed = await system.inbox_service.dismiss(
            workspace_key=workspace, inbox_item_id=second.id
        )
        pending = await system.inbox_service.list(workspace_key=workspace)
        all_items = await system.inbox_service.list(workspace_key=workspace, status="all")

        assert note.resolved_type == InboxResolvedType.NOTE
        assert dismissed.status == InboxStatus.DISMISSED
        assert pending.items == ()
        assert {item.id for item in all_items.items} == {first.id, second.id}
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_resolve_to_task_is_idempotent_and_workspace_scoped(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        item = await system.inbox_service.capture(
            workspace_key=workspace, content="跟进客户", source="api"
        )
        resolved = await system.inbox_service.resolve_to_task(
            workspace_key=workspace,
            inbox_item_id=item.id,
            title="跟进客户",
            due_at=NOW + timedelta(days=1),
        )
        tasks_before = await system.user_task_service.list(limit=100)

        with pytest.raises(FailureException) as repeat:
            await system.inbox_service.resolve_to_task(
                workspace_key=workspace, inbox_item_id=item.id, title="跟进客户"
            )
        tasks_after = await system.user_task_service.list(limit=100)
        with pytest.raises(FailureException) as mismatch:
            await system.inbox_service.get(
                workspace_key=WorkspaceKey(workspace_id="beta"), inbox_item_id=item.id
            )

        assert resolved.resolved_type == InboxResolvedType.USER_TASK
        assert repeat.value.failure.code == "inbox.already_resolved"
        assert repeat.value.failure.details["resolved_target_id"] == resolved.resolved_target_id
        assert [task.id for task in tasks_before] == [task.id for task in tasks_after]
        assert mismatch.value.failure.code == "inbox.workspace_mismatch"
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_resolve_to_reminder_and_work_log_use_existing_services(tmp_path):
    system = await _system(tmp_path)
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        reminder_item = await system.inbox_service.capture(
            workspace_key=workspace, content="提醒供应商", source="api"
        )
        work_log_item = await system.inbox_service.capture(
            workspace_key=workspace, content="完成验货", source="api"
        )
        reminder = await system.inbox_service.resolve_to_reminder(
            workspace_key=workspace,
            inbox_item_id=reminder_item.id,
            title="联系供应商",
            scheduled_at=NOW + timedelta(hours=3),
            timezone_name="Asia/Shanghai",
        )
        work_log = await system.inbox_service.resolve_to_work_log(
            workspace_key=workspace,
            inbox_item_id=work_log_item.id,
            title="完成验货",
        )

        stored_reminder = await system.reminder_service.get(reminder.resolved_target_id)
        assert stored_reminder.id == reminder.resolved_target_id
        assert work_log.resolved_type == InboxResolvedType.WORK_LOG
        assert work_log.resolved_target_id.startswith("inbox_wl_")
    finally:
        await system.shutdown()


@pytest.mark.asyncio
async def test_target_failure_leaves_inbox_pending(tmp_path, monkeypatch):
    system = await _system(tmp_path)
    workspace = WorkspaceKey()
    try:
        item = await system.inbox_service.capture(
            workspace_key=workspace, content="失败注入", source="api"
        )

        async def fail_create(**_kwargs):
            raise RuntimeError("injected target failure")

        monkeypatch.setattr(system.user_task_service, "create", fail_create)
        with pytest.raises(FailureException) as failure:
            await system.inbox_service.resolve_to_task(
                workspace_key=workspace, inbox_item_id=item.id, title="失败注入"
            )
        stored = await system.inbox_service.get(
            workspace_key=workspace, inbox_item_id=item.id
        )

        assert failure.value.failure.code == "inbox.resolve_failed"
        assert stored.status == InboxStatus.PENDING
        assert stored.resolved_target_id is None
    finally:
        await system.shutdown()

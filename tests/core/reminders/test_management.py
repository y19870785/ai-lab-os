from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.reminders import (
    ReminderInboxStatus,
    ReminderInboxTimeScope,
    ReminderInboxView,
    ReminderStatus,
)
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


pytestmark = pytest.mark.asyncio(loop_scope="function")


async def _system(tmp_path):
    clock = MutableClock(datetime(2026, 7, 17, 0, 0, tzinfo=timezone.utc))
    settings = make_test_settings(
        tmp_path,
        enable_scheduler=True,
        enable_reminders=True,
        timezone_name="Asia/Shanghai",
        scheduler_tick_interval=60,
    )
    system = await create_system(settings, clock=clock)
    await system.start()
    return system, clock


async def _create(system, title, due_at, workspace="default"):
    task = await system.user_task_service.create(
        title=title,
        due_at=due_at,
        timezone="Asia/Shanghai",
        metadata={
            "workspace": {
                "tenant_id": "tenant-a" if workspace != "default" else "default",
                "workspace_id": workspace,
                "namespace": "default",
            }
        },
    )
    return await system.reminder_bridge.create(
        user_task_id=task.id,
        remind_at=due_at,
        timezone_name="Asia/Shanghai",
    )


async def _settle(runtime):
    tasks = list(runtime._background_tasks)
    if tasks:
        await asyncio.gather(*tasks)
    await asyncio.sleep(0)


async def test_pending_view_excludes_terminal_but_explicit_upcoming_cancelled_works(tmp_path):
    system, clock = await _system(tmp_path)
    try:
        scheduled = await _create(system, "待处理", clock.now() + timedelta(hours=1))
        triggered = await _create(system, "已触发", clock.now() + timedelta(hours=2))
        cancelled = await _create(system, "已取消", clock.now() + timedelta(hours=3))
        await system.reminder_repository.trigger(
            triggered.id, triggered.remind_at, "management-test"
        )
        await system.reminder_management.cancel(
            workspace_key=WorkspaceKey(), reminder_id=cancelled.id
        )

        pending = await system.reminder_inbox.list(
            workspace_key=WorkspaceKey(), view=ReminderInboxView.PENDING
        )
        explicit_cancelled = await system.reminder_inbox.list(
            workspace_key=WorkspaceKey(),
            statuses={ReminderInboxStatus.CANCELLED},
            time_scope=ReminderInboxTimeScope.UPCOMING,
        )
        assert [item.reminder_id for item in pending.items] == [scheduled.id]
        assert [item.reminder_id for item in explicit_cancelled.items] == [cancelled.id]
    finally:
        await system.shutdown()


async def test_cancel_is_idempotent_and_prevents_occurrence(tmp_path):
    system, clock = await _system(tmp_path)
    try:
        reminder = await _create(system, "取消不触发", clock.now() + timedelta(hours=1))
        first = await system.reminder_management.cancel(
            workspace_key=WorkspaceKey(), reminder_id=reminder.id
        )
        second = await system.reminder_management.cancel(
            workspace_key=WorkspaceKey(), reminder_id=reminder.id
        )
        clock.advance(timedelta(hours=2))
        await system.scheduler_runtime._tick()
        await _settle(system.scheduler_runtime)
        assert first.current.status == second.current.status == "cancelled"
        assert second.previous_status == "cancelled"
        assert await system.reminder_service.list_occurrences(reminder.id) == []
    finally:
        await system.shutdown()


async def test_reschedule_reuses_job_is_idempotent_and_triggers_only_new_time(tmp_path):
    system, clock = await _system(tmp_path)
    try:
        old_due = clock.now() + timedelta(hours=1)
        new_due = clock.now() + timedelta(hours=2)
        reminder = await _create(system, "改期只触发一次", old_due)
        changed = await system.reminder_management.reschedule(
            workspace_key=WorkspaceKey(),
            reminder_id=reminder.id,
            remind_at=new_due,
            timezone_name="Asia/Shanghai",
            idempotency_key="reschedule-key",
        )
        repeated = await system.reminder_management.reschedule(
            workspace_key=WorkspaceKey(),
            reminder_id=reminder.id,
            remind_at=new_due,
            timezone_name="Asia/Shanghai",
            idempotency_key="reschedule-key",
        )
        with pytest.raises(FailureException) as conflict:
            await system.reminder_management.reschedule(
                workspace_key=WorkspaceKey(),
                reminder_id=reminder.id,
                remind_at=new_due + timedelta(hours=1),
                timezone_name="Asia/Shanghai",
                idempotency_key="reschedule-key",
            )
        assert changed.current.scheduler_job_id == reminder.scheduler_job_id
        assert repeated.current.revision == changed.current.revision
        assert conflict.value.failure.code == "reminder.idempotency_conflict"

        clock.advance(timedelta(hours=1, minutes=30))
        await system.scheduler_runtime._tick()
        await _settle(system.scheduler_runtime)
        assert await system.reminder_service.list_occurrences(reminder.id) == []

        clock.advance(timedelta(hours=1))
        await system.scheduler_runtime._tick()
        await _settle(system.scheduler_runtime)
        occurrences = await system.reminder_service.list_occurrences(reminder.id)
        assert len(occurrences) == 1
    finally:
        await system.shutdown()


async def test_resolver_fails_closed_for_workspace_not_found_and_ambiguity(tmp_path):
    system, clock = await _system(tmp_path)
    try:
        alpha = WorkspaceKey(tenant_id="tenant-a", workspace_id="alpha")
        beta = WorkspaceKey(tenant_id="tenant-a", workspace_id="beta")
        first = await _create(system, "联系张经理", clock.now() + timedelta(hours=1), "alpha")
        await _create(system, "联系张经理", clock.now() + timedelta(hours=2), "alpha")

        with pytest.raises(FailureException) as ambiguous:
            await system.reminder_management.resolve(
                workspace_key=alpha, title_query="联系张经理"
            )
        with pytest.raises(FailureException) as hidden:
            await system.reminder_management.resolve(
                workspace_key=beta, reminder_id=first.id
            )
        with pytest.raises(FailureException) as missing:
            await system.reminder_management.resolve(
                workspace_key=alpha, reminder_id="rem_missing"
            )
        assert ambiguous.value.failure.code == "reminder.ambiguous"
        assert len(ambiguous.value.failure.details["candidates"]) == 2
        assert hidden.value.failure.code == missing.value.failure.code == "reminder.not_found"
    finally:
        await system.shutdown()


async def test_unique_title_resolves_and_failed_reminder_can_be_rescheduled(tmp_path):
    system, clock = await _system(tmp_path)
    try:
        reminder = await _create(
            system, "联系张经理确认蜂蜡方案", clock.now() + timedelta(hours=1)
        )
        failure = FailureInfo(
            code="scheduler.delivery_failed",
            category=ErrorCategory.DEPENDENCY_FAILURE,
            message="Reminder delivery failed",
            component="scheduler",
            operation="execute",
            retryable=True,
        )
        failed = await system.reminder_service.transition(
            reminder,
            ReminderStatus.FAILED,
            failure=failure,
        )

        result = await system.reminder_management.reschedule(
            workspace_key=WorkspaceKey(),
            title_query="蜂蜡方案",
            remind_at=clock.now() + timedelta(hours=2),
            timezone_name="Asia/Shanghai",
        )
        stored = await system.reminder_service.get(failed.id)

        assert result.current.reminder_id == reminder.id
        assert result.current.status == "scheduled"
        assert stored.last_failure is None
        assert stored.metadata["management_reschedule"]["previous_failure_code"] == (
            "scheduler.delivery_failed"
        )
    finally:
        await system.shutdown()


async def test_management_maps_bridge_failures_without_fake_success(tmp_path, monkeypatch):
    system, clock = await _system(tmp_path)
    try:
        reminder = await _create(system, "故障注入", clock.now() + timedelta(hours=1))
        injected = FailureException(FailureInfo(
            code="scheduler.injected",
            category=ErrorCategory.DEPENDENCY_FAILURE,
            message="Injected scheduler failure",
            component="scheduler",
            operation="manage",
            retryable=True,
        ))

        async def fail_cancel(*args, **kwargs):
            raise injected

        async def fail_reschedule(*args, **kwargs):
            raise injected

        monkeypatch.setattr(system.reminder_bridge, "cancel", fail_cancel)
        with pytest.raises(FailureException) as cancel_failure:
            await system.reminder_management.cancel(
                workspace_key=WorkspaceKey(), reminder_id=reminder.id
            )
        monkeypatch.setattr(system.reminder_bridge, "reschedule", fail_reschedule)
        with pytest.raises(FailureException) as reschedule_failure:
            await system.reminder_management.reschedule(
                workspace_key=WorkspaceKey(),
                reminder_id=reminder.id,
                remind_at=clock.now() + timedelta(hours=2),
                timezone_name="Asia/Shanghai",
            )
        assert cancel_failure.value.failure.code == "reminder.cancellation_failed"
        assert reschedule_failure.value.failure.code == "reminder.rescheduling_failed"
        assert cancel_failure.value.failure.retryable is True
    finally:
        await system.shutdown()

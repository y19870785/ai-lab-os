from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from core.errors import ErrorCategory, FailureInfo
from core.reminders import ReminderInboxStatus, ReminderInboxTimeScope, ReminderStatus
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock


async def _create(system, title, due_at, workspace):
    task = await system.user_task_service.create(
        title=title,
        due_at=due_at,
        timezone="Asia/Shanghai",
        metadata={"workspace": workspace},
    )
    return await system.reminder_bridge.create(
        user_task_id=task.id,
        remind_at=due_at,
        timezone_name="Asia/Shanghai",
    )


def test_inbox_uses_stable_database_pagination_and_workspace_isolation(tmp_path):
    async def scenario():
        clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
        settings = make_test_settings(
            tmp_path, enable_scheduler=True, enable_reminders=True,
            timezone_name="Asia/Shanghai",
        )
        system = await create_system(settings, clock=clock)
        await system.start()
        try:
            alpha = {"tenant_id": "tenant-a", "workspace_id": "alpha", "namespace": "default"}
            beta = {"tenant_id": "tenant-a", "workspace_id": "beta", "namespace": "default"}
            first = await _create(system, "今天联系张经理", clock.now() + timedelta(hours=1), alpha)
            second = await _create(system, "明天整理报价", clock.now() + timedelta(days=1), alpha)
            await _create(system, "不可见提醒", clock.now() + timedelta(minutes=30), beta)

            key = WorkspaceKey(tenant_id="tenant-a", workspace_id="alpha")
            page1 = await system.reminder_inbox.list(workspace_key=key, limit=1, offset=0)
            page2 = await system.reminder_inbox.list(workspace_key=key, limit=1, offset=1)
            assert [item.reminder_id for item in page1.items] == [first.id]
            assert [item.reminder_id for item in page2.items] == [second.id]
            assert page1.has_more is True
            assert page2.has_more is False

            today = await system.reminder_inbox.list(
                workspace_key=key, time_scope=ReminderInboxTimeScope.TODAY,
            )
            upcoming = await system.reminder_inbox.list(
                workspace_key=key, time_scope=ReminderInboxTimeScope.UPCOMING,
            )
            assert [item.reminder_id for item in today.items] == [first.id]
            assert {item.reminder_id for item in upcoming.items} == {first.id, second.id}
        finally:
            await system.shutdown()

    asyncio.run(scenario())


def test_inbox_status_filter_uses_shared_aggregated_status(tmp_path):
    async def scenario():
        clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
        settings = make_test_settings(
            tmp_path, enable_scheduler=True, enable_reminders=True,
            timezone_name="Asia/Shanghai",
        )
        system = await create_system(settings, clock=clock)
        await system.start()
        try:
            workspace = {"tenant_id": "default", "workspace_id": "default", "namespace": "default"}
            reminder = await _create(
                system, "已触发提醒", clock.now() + timedelta(hours=1), workspace
            )
            await system.reminder_repository.trigger(reminder.id, reminder.remind_at, "inbox-test")
            page = await system.reminder_inbox.list(
                workspace_key=WorkspaceKey(), statuses={ReminderInboxStatus.TRIGGERED},
            )
            assert page.count == 1
            assert page.items[0].status == ReminderInboxStatus.TRIGGERED
            assert page.items[0].occurrence_id

            failed = await _create(
                system, "失败提醒", clock.now() + timedelta(hours=2), workspace
            )
            failure = FailureInfo(
                code="reminder.test_failure",
                category=ErrorCategory.EXECUTION_FAILURE,
                message="Injected test failure",
                component="reminder.handler",
                operation="trigger",
                retryable=False,
            )
            await system.reminder_service.transition(
                failed, ReminderStatus.FAILED, failure=failure
            )
            failed_page = await system.reminder_inbox.list(
                workspace_key=WorkspaceKey(), statuses={ReminderInboxStatus.FAILED},
            )
            assert failed_page.items[0].last_failure_code == "reminder.test_failure"

            retrying = await _create(
                system, "重试提醒", clock.now() + timedelta(hours=3), workspace
            )
            claim_at = retrying.remind_at + timedelta(seconds=1)
            claimed = await system.scheduler_runtime._persistence.claim_job(
                retrying.scheduler_job_id,
                now=claim_at,
                claim_token="inbox-retry-claim",
                claim_expires_at=claim_at + timedelta(seconds=1),
                run_id="inbox-retry-run",
            )
            assert claimed is not None
            await system.scheduler_runtime._persistence.release_expired_claims(
                claim_at + timedelta(seconds=2), retry_delay_seconds=60
            )
            retrying_page = await system.reminder_inbox.list(
                workspace_key=WorkspaceKey(), statuses={ReminderInboxStatus.RETRYING},
            )
            assert [item.reminder_id for item in retrying_page.items] == [retrying.id]

            cancelled = await _create(
                system, "取消提醒", clock.now() + timedelta(hours=4), workspace
            )
            await system.reminder_bridge.cancel(cancelled.id)
            cancelled_page = await system.reminder_inbox.list(
                workspace_key=WorkspaceKey(), statuses={ReminderInboxStatus.CANCELLED},
            )
            assert [item.reminder_id for item in cancelled_page.items] == [cancelled.id]
        finally:
            await system.shutdown()

    asyncio.run(scenario())

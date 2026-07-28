"""Focused source doubles and builders for Daily Review tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from core.daily_review import DailyReviewService
from core.inbox import InboxItem, InboxStatus
from core.reminders import ReminderInboxItem, ReminderInboxStatus
from core.user_tasks import UserTask, UserTaskStatus
from core.waiting_for import WaitingFor, WaitingForStatus
from core.work_log import WorkLogRecord, WorkLogSource, WorkLogStatus
from core.workspace.models import WorkspaceKey

WORKSPACE = WorkspaceKey(
    tenant_id="tenant-a",
    workspace_id="workspace-a",
    namespace="namespace-a",
    trace_id="trace-daily-review",
)


class FrozenCountingClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.instant


class PagedService:
    def __init__(self, items: list[Any] | None = None) -> None:
        self.items = list(items or [])
        self.calls: list[dict[str, Any]] = []

    async def list(self, **kwargs):
        self.calls.append(kwargs)
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit")
        query = kwargs.get("query")
        if query is not None:
            offset = query.offset
            limit = query.limit
        limit = limit or 100
        page_items = self.items[offset:offset + limit]
        return SimpleNamespace(
            items=tuple(page_items),
            count=len(page_items),
            has_more=offset + len(page_items) < len(self.items),
        )


class UserTaskServiceDouble:
    def __init__(self, items: list[UserTask] | None = None) -> None:
        self.items = list(items or [])
        self.calls: list[dict[str, Any]] = []

    async def list(self, **kwargs) -> list[UserTask]:
        self.calls.append(kwargs)
        query = kwargs["query"]
        as_of = kwargs["as_of"]
        items = list(self.items)
        if query.status is not None:
            items = [item for item in items if item.status == query.status]
        if query.completed_from is not None:
            items = [
                item for item in items
                if item.completed_at is not None
                and item.completed_at >= query.completed_from
            ]
        if query.completed_to is not None:
            items = [
                item for item in items
                if item.completed_at is not None
                and item.completed_at < query.completed_to
            ]
        if query.cancelled_from is not None:
            items = [
                item for item in items
                if item.cancelled_at is not None
                and item.cancelled_at >= query.cancelled_from
            ]
        if query.cancelled_to is not None:
            items = [
                item for item in items
                if item.cancelled_at is not None
                and item.cancelled_at < query.cancelled_to
            ]
        if query.overdue is not None:
            items = [
                item for item in items
                if bool(
                    item.status == UserTaskStatus.ACTIVE
                    and item.due_at is not None
                    and item.due_at < as_of
                ) == query.overdue
            ]
        if query.due_from is not None:
            items = [
                item for item in items
                if item.due_at is not None and item.due_at >= query.due_from
            ]
        if query.due_to is not None:
            items = [
                item for item in items
                if item.due_at is not None and item.due_at <= query.due_to
            ]
        return items[query.offset:query.offset + query.limit]


class FailingService:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.calls = 0

    async def list(self, **kwargs):
        self.calls += 1
        raise self.exc


@dataclass
class SourceSet:
    work_logs: Any
    waiting_for: Any
    reminders: Any
    inbox: Any
    user_tasks: Any


def empty_sources() -> SourceSet:
    return SourceSet(
        work_logs=PagedService(),
        waiting_for=PagedService(),
        reminders=PagedService(),
        inbox=PagedService(),
        user_tasks=UserTaskServiceDouble(),
    )


def make_service(
    clock: FrozenCountingClock,
    sources: SourceSet | None = None,
    *,
    timezone_name: str = "UTC",
    enabled: bool = True,
    user_tasks_enabled: bool = True,
    reminders_enabled: bool = True,
) -> DailyReviewService:
    resolved = sources or empty_sources()
    return DailyReviewService(
        work_log_service=resolved.work_logs,
        waiting_for_service=resolved.waiting_for,
        reminder_inbox=resolved.reminders,
        inbox_service=resolved.inbox,
        user_task_service=resolved.user_tasks,
        clock=clock,
        timezone_name=timezone_name,
        enabled=enabled,
        user_tasks_enabled=user_tasks_enabled,
        reminders_enabled=reminders_enabled,
    )


def work_log(
    item_id: str,
    *,
    occurred_at: datetime,
    status: WorkLogStatus = WorkLogStatus.COMPLETED,
    title: str | None = None,
) -> WorkLogRecord:
    return WorkLogRecord(
        id=item_id,
        workspace_key=WORKSPACE,
        occurred_at=occurred_at,
        timezone="UTC",
        subject=title or item_id,
        raw_text=title or item_id,
        status=status,
        source=WorkLogSource.API,
        created_at=occurred_at,
        schema_version=0 if item_id.startswith("wl_legacy_") else 1,
    )


def waiting_for(
    item_id: str,
    *,
    now: datetime,
    status: WaitingForStatus = WaitingForStatus.OPEN,
    expected_by: datetime | None = None,
    next_review_at: datetime | None = None,
    resolved_at: datetime | None = None,
    cancelled_at: datetime | None = None,
) -> WaitingFor:
    return WaitingFor(
        id=item_id,
        workspace_key=WORKSPACE,
        subject=item_id,
        waiting_on="external",
        status=status,
        expected_by=expected_by,
        next_review_at=next_review_at,
        source="test",
        created_at=now,
        updated_at=resolved_at or cancelled_at or now,
        resolved_at=resolved_at,
        cancelled_at=cancelled_at,
    )


def reminder(
    item_id: str,
    *,
    scheduled_for: datetime,
    status: ReminderInboxStatus,
    triggered_at: datetime | None = None,
) -> ReminderInboxItem:
    return ReminderInboxItem(
        reminder_id=item_id,
        task_id=f"ut_{item_id[4:]}",
        task_title=item_id,
        status=status,
        scheduled_for=scheduled_for,
        timezone="UTC",
        triggered_at=triggered_at,
    )


def inbox(
    item_id: str,
    *,
    created_at: datetime,
) -> InboxItem:
    return InboxItem(
        id=item_id,
        workspace_key=WORKSPACE,
        content=item_id,
        source="test",
        status=InboxStatus.PENDING,
        created_at=created_at,
        updated_at=created_at,
    )


def user_task(
    item_id: str,
    *,
    now: datetime,
    status: UserTaskStatus = UserTaskStatus.ACTIVE,
    due_at: datetime | None = None,
    completed_at: datetime | None = None,
    cancelled_at: datetime | None = None,
) -> UserTask:
    return UserTask(
        id=item_id,
        title=item_id,
        status=status,
        due_at=due_at,
        created_at=now,
        updated_at=completed_at or cancelled_at or now,
        completed_at=completed_at,
        cancelled_at=cancelled_at,
        metadata={
            "workspace": {
                "tenant_id": WORKSPACE.tenant_id,
                "workspace_id": WORKSPACE.workspace_id,
                "namespace": WORKSPACE.namespace,
            }
        },
    )


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)

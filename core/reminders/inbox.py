"""Persistent Reminder inbox query boundary."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from core.clock import Clock
from core.reminders.orchestration import build_reminder_status_view
from core.workspace.models import WorkspaceKey


class ReminderInboxStatus(str, Enum):
    SCHEDULED = "scheduled"
    RETRYING = "retrying"
    TRIGGERED = "triggered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderInboxTimeScope(str, Enum):
    TODAY = "today"
    UPCOMING = "upcoming"


class ReminderInboxItem(BaseModel):
    reminder_id: str
    task_id: str
    task_title: str
    status: ReminderInboxStatus
    scheduled_for: datetime
    timezone: str
    scheduler_job_id: str | None = None
    scheduler_status: str | None = None
    occurrence_id: str | None = None
    occurrence_status: str | None = None
    triggered_at: datetime | None = None
    last_failure_code: str | None = None


class ReminderInboxPage(BaseModel):
    items: list[ReminderInboxItem]
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
    count: int = Field(ge=0)
    has_more: bool
    filter: dict[str, Any] = Field(default_factory=dict)


def normalized_workspace(key: WorkspaceKey) -> dict[str, str]:
    return {
        "tenant_id": key.tenant_id or "default",
        "workspace_id": key.workspace_id or "default",
        "namespace": key.namespace or "default",
    }


def task_belongs_to_workspace(task, key: WorkspaceKey) -> bool:
    expected = normalized_workspace(key)
    stored = task.metadata.get("workspace")
    if not isinstance(stored, dict):
        return expected == {
            "tenant_id": "default",
            "workspace_id": "default",
            "namespace": "default",
        }
    actual = {
        "tenant_id": str(stored.get("tenant_id") or "default"),
        "workspace_id": str(stored.get("workspace_id") or "default"),
        "namespace": str(stored.get("namespace") or "default"),
    }
    return actual == expected


class ReminderInboxService:
    """Build bounded inbox pages from persisted Reminder-related services."""

    _SCAN_BATCH_SIZE = 100

    def __init__(
        self,
        user_tasks,
        reminder_service,
        scheduler_runtime,
        clock: Clock,
        timezone_name: str,
    ) -> None:
        self._user_tasks = user_tasks
        self._reminders = reminder_service
        self._scheduler = scheduler_runtime
        self._clock = clock
        self._zone = ZoneInfo(timezone_name)

    async def list(
        self,
        *,
        workspace_key: WorkspaceKey,
        statuses: set[ReminderInboxStatus] | None = None,
        time_scope: ReminderInboxTimeScope | None = None,
        limit: int = 20,
        offset: int = 0,
        trace_id: str = "",
    ) -> ReminderInboxPage:
        remind_from, remind_to = self._time_bounds(time_scope)
        scan_offset = 0
        matching_seen = 0
        items: list[ReminderInboxItem] = []

        while len(items) <= limit:
            batch = await self._reminders.list_page(
                remind_from=remind_from,
                remind_to=remind_to,
                limit=self._SCAN_BATCH_SIZE,
                offset=scan_offset,
                trace_id=trace_id,
            )
            if not batch:
                break
            scan_offset += len(batch)
            for reminder in batch:
                task = await self._user_tasks.get(reminder.user_task_id, trace_id)
                if not task_belongs_to_workspace(task, workspace_key):
                    continue
                job = (
                    await self._scheduler.get_job(reminder.scheduler_job_id)
                    if reminder.scheduler_job_id else None
                )
                occurrences = await self._reminders.list_occurrences(reminder.id, trace_id)
                occurrence = occurrences[-1] if occurrences else None
                view = build_reminder_status_view(reminder, task, job, occurrence)
                item_status = ReminderInboxStatus(view.status)
                if statuses and item_status not in statuses:
                    continue
                if matching_seen < offset:
                    matching_seen += 1
                    continue
                matching_seen += 1
                items.append(ReminderInboxItem(
                    reminder_id=view.reminder_id,
                    task_id=view.task_id,
                    task_title=view.task_title,
                    status=item_status,
                    scheduled_for=view.scheduled_for,
                    timezone=view.timezone,
                    scheduler_job_id=view.scheduler_job_id,
                    scheduler_status=view.scheduler_status,
                    occurrence_id=view.occurrence_id,
                    occurrence_status=view.occurrence_status,
                    triggered_at=view.triggered_at,
                    last_failure_code=view.last_failure.code if view.last_failure else None,
                ))
                if len(items) > limit:
                    break
            if len(items) > limit or len(batch) < self._SCAN_BATCH_SIZE:
                break

        has_more = len(items) > limit
        page_items = items[:limit]
        return ReminderInboxPage(
            items=page_items,
            limit=limit,
            offset=offset,
            count=len(page_items),
            has_more=has_more,
            filter={
                "statuses": sorted(status.value for status in statuses) if statuses else [],
                "time_scope": time_scope.value if time_scope else None,
            },
        )

    def _time_bounds(
        self, time_scope: ReminderInboxTimeScope | None
    ) -> tuple[datetime | None, datetime | None]:
        if time_scope == ReminderInboxTimeScope.UPCOMING:
            return self._clock.now().astimezone(timezone.utc), None
        if time_scope == ReminderInboxTimeScope.TODAY:
            local_now = self._clock.now().astimezone(self._zone)
            local_start = datetime.combine(local_now.date(), time.min, tzinfo=self._zone)
            return (
                local_start.astimezone(timezone.utc),
                (local_start + timedelta(days=1)).astimezone(timezone.utc),
            )
        return None, None

"""Shared Reminder management boundary for API, CLI, and applications."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import BaseModel

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.reminders.inbox import (
    ReminderInboxStatus,
    ReminderInboxView,
    task_belongs_to_workspace,
)
from core.reminders.models import Reminder, ReminderStatus
from core.reminders.orchestration import ReminderStatusView, build_reminder_status_view
from core.user_tasks import UserTask
from core.workspace.models import WorkspaceKey


class ReminderManagementResult(BaseModel):
    action: str
    previous_status: str
    previous_scheduled_for: datetime
    current: ReminderStatusView


@dataclass(frozen=True)
class ReminderResolution:
    reminder: Reminder
    task: UserTask
    view: ReminderStatusView


class ReminderManagementService:
    """Coordinate Reminder management without duplicating the Scheduler Saga."""

    COMPONENT = "reminder.management"

    def __init__(self, user_tasks, reminders, bridge, scheduler, inbox) -> None:
        self._user_tasks = user_tasks
        self._reminders = reminders
        self._bridge = bridge
        self._scheduler = scheduler
        self._inbox = inbox

    @staticmethod
    def _raise(
        code: str,
        category: ErrorCategory,
        message: str,
        operation: str,
        trace_id: str,
        *,
        retryable: bool = False,
        details: dict | None = None,
    ) -> None:
        raise FailureException(FailureInfo(
            code=code,
            category=category,
            message=message,
            component=ReminderManagementService.COMPONENT,
            operation=operation,
            retryable=retryable,
            trace_id=trace_id,
            details=details or {},
        ))

    async def _view(self, reminder: Reminder, task, trace_id: str) -> ReminderStatusView:
        job = (
            await self._scheduler.get_job(reminder.scheduler_job_id)
            if reminder.scheduler_job_id else None
        )
        occurrences = await self._reminders.list_occurrences(reminder.id, trace_id)
        occurrence = occurrences[-1] if occurrences else None
        return build_reminder_status_view(reminder, task, job, occurrence)

    async def _by_id(
        self, reminder_id: str, workspace_key: WorkspaceKey, trace_id: str
    ) -> ReminderResolution:
        try:
            reminder = await self._reminders.get(reminder_id, trace_id)
            task = await self._user_tasks.get(reminder.user_task_id, trace_id)
        except FailureException as exc:
            if exc.failure.category == ErrorCategory.NOT_FOUND:
                self._raise(
                    "reminder.not_found", ErrorCategory.NOT_FOUND,
                    "Reminder was not found", "resolve", trace_id,
                )
            raise
        if not task_belongs_to_workspace(task, workspace_key):
            self._raise(
                "reminder.not_found", ErrorCategory.NOT_FOUND,
                "Reminder was not found", "resolve", trace_id,
            )
        return ReminderResolution(reminder, task, await self._view(reminder, task, trace_id))

    async def resolve(
        self,
        *,
        workspace_key: WorkspaceKey,
        reminder_id: str | None = None,
        title_query: str | None = None,
        allowed_statuses: set[str] | None = None,
        trace_id: str = "",
    ) -> ReminderResolution:
        if reminder_id:
            resolution = await self._by_id(reminder_id, workspace_key, trace_id)
            if allowed_statuses and resolution.view.status not in allowed_statuses:
                self._raise(
                    "reminder.not_found", ErrorCategory.NOT_FOUND,
                    "Reminder was not found", "resolve", trace_id,
                )
            return resolution

        query = (title_query or "").strip().casefold()
        if not query:
            self._raise(
                "reminder.not_found", ErrorCategory.NOT_FOUND,
                "Reminder was not found", "resolve", trace_id,
            )

        candidates = []
        offset = 0
        while True:
            page = await self._inbox.list(
                workspace_key=workspace_key,
                limit=100,
                offset=offset,
                trace_id=trace_id,
            )
            for item in page.items:
                if allowed_statuses and item.status.value not in allowed_statuses:
                    continue
                if query in item.task_title.casefold():
                    candidates.append(item)
            if not page.has_more:
                break
            offset += page.count

        exact = [item for item in candidates if item.task_title.strip().casefold() == query]
        matches = exact or candidates
        if not matches:
            self._raise(
                "reminder.not_found", ErrorCategory.NOT_FOUND,
                "Reminder was not found", "resolve", trace_id,
            )
        if len(matches) > 1:
            self._raise(
                "reminder.ambiguous", ErrorCategory.CONFLICT,
                "Multiple reminders matched; specify a Reminder ID", "resolve", trace_id,
                details={
                    "candidates": [
                        {
                            "reminder_id": item.reminder_id,
                            "task_title": item.task_title,
                            "scheduled_for": item.scheduled_for.isoformat(),
                            "status": item.status.value,
                        }
                        for item in matches[:20]
                    ]
                },
            )
        return await self._by_id(matches[0].reminder_id, workspace_key, trace_id)

    async def status(
        self,
        *,
        workspace_key: WorkspaceKey,
        reminder_id: str | None = None,
        title_query: str | None = None,
        trace_id: str = "",
    ) -> ReminderStatusView:
        return (await self.resolve(
            workspace_key=workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            trace_id=trace_id,
        )).view

    async def cancel(
        self,
        *,
        workspace_key: WorkspaceKey,
        reminder_id: str | None = None,
        title_query: str | None = None,
        trace_id: str = "",
    ) -> ReminderManagementResult:
        resolution = await self.resolve(
            workspace_key=workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            trace_id=trace_id,
        )
        if resolution.reminder.status in {ReminderStatus.TRIGGERED, ReminderStatus.FAILED}:
            self._raise(
                "reminder.terminal_state", ErrorCategory.CONFLICT,
                "Terminal Reminder cannot be cancelled", "cancel", trace_id,
                details={"reminder_id": resolution.reminder.id},
            )
        try:
            reminder = await self._bridge.cancel(resolution.reminder.id, trace_id)
        except FailureException as exc:
            self._raise(
                "reminder.cancellation_failed", exc.failure.category,
                "Reminder cancellation failed", "cancel", trace_id,
                retryable=exc.failure.retryable,
                details={"reminder_id": resolution.reminder.id},
            )
        current = await self._by_id(reminder.id, workspace_key, trace_id)
        return ReminderManagementResult(
            action="cancel",
            previous_status=resolution.view.status,
            previous_scheduled_for=resolution.view.scheduled_for,
            current=current.view,
        )

    async def reschedule(
        self,
        *,
        workspace_key: WorkspaceKey,
        remind_at: datetime,
        timezone_name: str,
        reminder_id: str | None = None,
        title_query: str | None = None,
        expected_revision: int | None = None,
        idempotency_key: str = "",
        trace_id: str = "",
    ) -> ReminderManagementResult:
        resolution = await self.resolve(
            workspace_key=workspace_key,
            reminder_id=reminder_id,
            title_query=title_query,
            trace_id=trace_id,
        )
        if resolution.reminder.status in {ReminderStatus.TRIGGERED, ReminderStatus.CANCELLED}:
            self._raise(
                "reminder.terminal_state", ErrorCategory.CONFLICT,
                "Terminal Reminder cannot be rescheduled", "reschedule", trace_id,
                details={"reminder_id": resolution.reminder.id},
            )

        target = remind_at.astimezone(timezone.utc).isoformat()
        operation_metadata = {
            "target": target,
            "previous_failure_code": (
                resolution.reminder.last_failure.code
                if resolution.reminder.last_failure else ""
            ),
        }
        key = idempotency_key.strip()
        if key:
            key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()
            previous = resolution.reminder.metadata.get("management_reschedule")
            if isinstance(previous, dict) and previous.get("key_hash") == key_hash:
                if previous.get("target") != target:
                    self._raise(
                        "reminder.idempotency_conflict", ErrorCategory.CONFLICT,
                        "Idempotency key was already used for another schedule",
                        "reschedule", trace_id,
                    )
                if (
                    resolution.reminder.status == ReminderStatus.SCHEDULED
                    and resolution.reminder.remind_at.isoformat() == target
                ):
                    return ReminderManagementResult(
                        action="reschedule",
                        previous_status=resolution.view.status,
                        previous_scheduled_for=resolution.view.scheduled_for,
                        current=resolution.view,
                    )
            operation_metadata["key_hash"] = key_hash

        try:
            reminder = await self._bridge.reschedule(
                resolution.reminder.id,
                remind_at=remind_at,
                timezone_name=timezone_name,
                expected_revision=expected_revision,
                trace_id=trace_id,
                management_metadata=operation_metadata,
            )
        except FailureException as exc:
            self._raise(
                "reminder.rescheduling_failed", exc.failure.category,
                "Reminder rescheduling failed", "reschedule", trace_id,
                retryable=exc.failure.retryable,
                details={"reminder_id": resolution.reminder.id},
            )
        current = await self._by_id(reminder.id, workspace_key, trace_id)
        return ReminderManagementResult(
            action="reschedule",
            previous_status=resolution.view.status,
            previous_scheduled_for=resolution.view.scheduled_for,
            current=current.view,
        )

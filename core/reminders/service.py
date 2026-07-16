"""Reminder domain service; scheduling orchestration lives in the bridge."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from core.clock import Clock, SystemClock
from core.errors import (
    ErrorCategory,
    FailureException,
    FailureInfo,
    failure_from_exception,
)
from core.reminders.events import publish_reminder_event
from core.reminders.exceptions import (
    ReminderConflictError,
    ReminderNotFoundError,
    ReminderUnavailableError,
)
from core.reminders.models import Reminder, ReminderStatus, utc_now
from core.user_tasks import UserTaskStatus


_LOGGER = logging.getLogger(__name__)


class ReminderService:
    COMPONENT = "reminders"

    def __init__(self, repository, user_task_service, bus=None, clock: Clock | None = None) -> None:
        self._repository = repository
        self._user_tasks = user_task_service
        self._bus = bus
        self._clock = clock or SystemClock()

    async def initialize(self) -> None:
        try:
            await self._repository.initialize()
        except Exception as exc:
            self._raise(exc, "initialize", "")

    async def close(self) -> None:
        await self._repository.close()

    def _raise(
        self,
        exc: Exception,
        operation: str,
        trace_id: str,
        *,
        reminder_id: str = "",
        recovery_state: str = "",
    ) -> None:
        if isinstance(exc, FailureException):
            raise exc
        category = (
            ErrorCategory.NOT_FOUND
            if isinstance(exc, ReminderNotFoundError)
            else ErrorCategory.CONFLICT
            if isinstance(exc, ReminderConflictError)
            else ErrorCategory.VALIDATION
            if isinstance(exc, (ValidationError, ValueError))
            else ErrorCategory.NOT_CONFIGURED
            if isinstance(exc, ReminderUnavailableError)
            else ErrorCategory.PERSISTENCE_FAILURE
        )
        failure = failure_from_exception(
            exc,
            component=self.COMPONENT,
            operation=operation,
            trace_id=trace_id,
            code=f"reminders.{operation}.{category.value}",
            category=category,
            retryable=category in {
                ErrorCategory.PERSISTENCE_FAILURE,
                ErrorCategory.NOT_CONFIGURED,
            },
            details={
                key: value for key, value in {
                    "reminder_id": reminder_id,
                    "recovery_state": recovery_state,
                }.items() if value
            },
        ).model_copy(update={"message": f"Reminder {operation} failed"})
        raise FailureException(failure) from exc

    async def create_pending(
        self,
        *,
        user_task_id: str,
        remind_at: datetime,
        timezone_name: str,
        trace_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> Reminder:
        try:
            task = await self._user_tasks.get(user_task_id, trace_id)
            if task.status != UserTaskStatus.ACTIVE:
                raise ReminderConflictError("Terminal UserTask cannot receive a Reminder")
            reminder = Reminder(
                user_task_id=user_task_id,
                remind_at=remind_at,
                timezone=timezone_name,
                trace_id=trace_id,
                metadata=metadata or {},
            )
            if reminder.remind_at <= self._clock.now():
                raise ValueError("remind_at must be in the future")
            result = await self._repository.create(reminder)
            await self._publish("reminder.created", result)
            return result
        except Exception as exc:
            self._raise(exc, "create", trace_id)

    async def get(self, reminder_id: str, trace_id: str = "") -> Reminder:
        try:
            return await self._repository.get(reminder_id)
        except Exception as exc:
            self._raise(exc, "get", trace_id, reminder_id=reminder_id)

    async def list_for_task(self, task_id: str, trace_id: str = "") -> list[Reminder]:
        try:
            await self._user_tasks.get(task_id, trace_id)
            return await self._repository.list_for_task(task_id)
        except Exception as exc:
            self._raise(exc, "list", trace_id)

    async def list_page(
        self,
        *,
        remind_from: datetime | None = None,
        remind_to: datetime | None = None,
        limit: int,
        offset: int,
        trace_id: str = "",
    ) -> list[Reminder]:
        try:
            return await self._repository.list_page(
                remind_from=remind_from,
                remind_to=remind_to,
                limit=limit,
                offset=offset,
            )
        except Exception as exc:
            self._raise(exc, "list", trace_id)

    async def list_occurrences(self, reminder_id: str, trace_id: str = ""):
        await self.get(reminder_id, trace_id)
        try:
            return await self._repository.list_occurrences(reminder_id)
        except Exception as exc:
            self._raise(exc, "list_occurrences", trace_id, reminder_id=reminder_id)

    async def transition(
        self,
        reminder: Reminder,
        status: ReminderStatus,
        *,
        scheduler_job_id: str | None | object = ...,
        failure: FailureInfo | None | object = ...,
        trace_id: str = "",
    ) -> Reminder:
        changes: dict[str, Any] = {"status": status, "trace_id": trace_id or reminder.trace_id}
        if scheduler_job_id is not ...:
            changes["scheduler_job_id"] = scheduler_job_id
        if failure is not ...:
            changes["last_failure"] = failure
        if status == ReminderStatus.CANCELLED:
            changes["cancelled_at"] = utc_now()
        candidate = reminder.model_copy(update=changes)
        try:
            result = await self._repository.update(candidate, reminder.revision)
            event = {
                ReminderStatus.SCHEDULED: "reminder.scheduled",
                ReminderStatus.PENDING_RESCHEDULE: "reminder.reschedule.pending",
                ReminderStatus.PENDING_CANCEL: "reminder.cancel.pending",
                ReminderStatus.CANCELLED: "reminder.cancelled",
                ReminderStatus.FAILED: "reminder.failed",
            }.get(status)
            if event:
                await self._publish(event, result)
            return result
        except Exception as exc:
            self._raise(
                exc,
                "transition",
                trace_id,
                reminder_id=reminder.id,
                recovery_state=status.value,
            )

    async def prepare_reschedule(
        self,
        reminder_id: str,
        *,
        remind_at: datetime,
        timezone_name: str,
        expected_revision: int | None,
        trace_id: str,
    ) -> Reminder:
        reminder = await self.get(reminder_id, trace_id)
        if reminder.status in {ReminderStatus.TRIGGERED, ReminderStatus.CANCELLED}:
            self._raise(
                ReminderConflictError("Terminal Reminder cannot be rescheduled"),
                "reschedule",
                trace_id,
                reminder_id=reminder_id,
            )
        if expected_revision is not None and expected_revision != reminder.revision:
            self._raise(
                ReminderConflictError("Reminder was modified concurrently"),
                "reschedule",
                trace_id,
                reminder_id=reminder_id,
            )
        try:
            candidate = Reminder.model_validate({
                **reminder.model_dump(),
                "remind_at": remind_at,
                "timezone": timezone_name,
                "status": ReminderStatus.PENDING_RESCHEDULE,
                "last_failure": None,
                "trace_id": trace_id or reminder.trace_id,
            })
            if candidate.remind_at <= self._clock.now():
                raise ValueError("remind_at must be in the future")
            return await self._repository.update(candidate, reminder.revision)
        except Exception as exc:
            self._raise(exc, "reschedule", trace_id, reminder_id=reminder_id)

    async def health(self) -> dict[str, object]:
        return await self._repository.health_check()

    async def _publish(self, event_type: str, reminder: Reminder) -> None:
        if self._bus is None or not getattr(self._bus, "is_running", False):
            return
        try:
            await publish_reminder_event(
                self._bus,
                event_type,
                reminder_id=reminder.id,
                user_task_id=reminder.user_task_id,
                status=reminder.status.value,
                trace_id=reminder.trace_id,
            )
            self._repository.clear_observability_degraded()
        except Exception:
            self._repository.mark_observability_degraded("event_publish_failed")
            _LOGGER.warning(
                "reminder.event.publish_failed",
                extra={"event_type": event_type, "reminder_id": reminder.id},
            )

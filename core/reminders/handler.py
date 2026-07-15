"""Scheduler action handler for effectively-once Reminder occurrences."""

from __future__ import annotations

from datetime import datetime

from core.reminders.events import publish_reminder_event
from core.reminders.exceptions import ReminderConflictError
from core.reminders.models import ReminderStatus
from core.errors import ErrorCategory, failure_from_exception


class ReminderActionHandler:
    def __init__(self, repository, bus=None) -> None:
        self._repository = repository
        self._bus = bus

    async def execute(self, job, run):
        reminder_id = str(job.action_payload.get("reminder_id", ""))
        scheduled_raw = str(job.action_payload.get("scheduled_at", ""))
        if not reminder_id or not scheduled_raw:
            raise ValueError("Reminder action requires reminder_id and scheduled_at")
        scheduled_at = datetime.fromisoformat(scheduled_raw)
        if scheduled_at.tzinfo is None or scheduled_at.utcoffset() is None:
            raise ValueError("Reminder scheduled_at must include timezone information")
        try:
            reminder, occurrence, idempotent = await self._repository.trigger(
                reminder_id, scheduled_at, run.trace_id
            )
        except ReminderConflictError:
            reminder = await self._repository.get(reminder_id)
            if reminder.status not in {
                ReminderStatus.CANCELLED,
                ReminderStatus.PENDING_CANCEL,
            }:
                raise
            return {
                "reminder_id": reminder.id,
                "status": reminder.status.value,
                "idempotent": True,
            }
        except Exception as exc:
            failure = failure_from_exception(
                exc,
                component="reminder_handler",
                operation="trigger",
                trace_id=run.trace_id,
                code="reminders.trigger.failed",
                category=ErrorCategory.PERSISTENCE_FAILURE,
                retryable=True,
                details={"reminder_id": reminder_id, "attempt": run.attempt},
            ).model_copy(update={"message": "Reminder trigger failed"})
            await self._repository.record_trigger_failure(
                reminder_id, scheduled_at, run.trace_id, failure
            )
            try:
                reminder = await self._repository.get(reminder_id)
                await publish_reminder_event(
                    self._bus,
                    "reminder.failed",
                    reminder_id=reminder.id,
                    user_task_id=reminder.user_task_id,
                    status=reminder.status.value,
                    trace_id=run.trace_id,
                )
            except Exception:
                self._repository.mark_observability_degraded("failure_event_unavailable")
            raise

        try:
            await publish_reminder_event(
                self._bus,
                "reminder.triggered",
                reminder_id=reminder.id,
                user_task_id=reminder.user_task_id,
                occurrence_id=occurrence.id,
                status=reminder.status.value,
                trace_id=run.trace_id,
            )
            self._repository.clear_observability_degraded()
        except Exception as exc:
            # The database transaction is authoritative; EventBus is observability only.
            self._repository.mark_observability_degraded(exc.__class__.__name__)
        return {
            "reminder_id": reminder.id,
            "occurrence_id": occurrence.id,
            "status": reminder.status.value,
            "idempotent": idempotent,
        }

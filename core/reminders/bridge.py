"""Saga bridge between durable Reminders and Scheduler jobs."""

from __future__ import annotations

import logging
from datetime import datetime

from core.errors import (
    ErrorCategory,
    FailureException,
    FailureInfo,
    RuntimeStatus,
    failure_from_exception,
)
from core.reminders.exceptions import ReminderConflictError, ReminderUnavailableError
from core.reminders.models import ReconciliationResult, Reminder, ReminderStatus
from core.scheduler.models import JobStatus, ScheduleRequest, Trigger, TriggerType
from core.user_tasks import UserTaskStatus


_LOGGER = logging.getLogger(__name__)


class ReminderSchedulerBridge:
    """Coordinate two databases with explicit recoverable Saga states."""

    def __init__(self, service, repository, scheduler_runtime, user_task_service) -> None:
        self._service = service
        self._repository = repository
        self._scheduler = scheduler_runtime
        self._user_tasks = user_task_service
        self._initialized = False
        self._last_reconciliation: ReconciliationResult | None = None

    async def initialize(self) -> ReconciliationResult:
        self._initialized = True
        if self._scheduler is None:
            self._last_reconciliation = ReconciliationResult()
            return self._last_reconciliation
        return await self.reconcile()

    def _require_scheduler(self) -> None:
        if self._scheduler is None:
            raise ReminderUnavailableError("Scheduler is disabled or not configured")

    @staticmethod
    def _payload(reminder: Reminder) -> dict[str, object]:
        return {
            "reminder_id": reminder.id,
            "scheduled_at": reminder.remind_at.isoformat(),
        }

    async def _create_job(self, reminder: Reminder):
        self._require_scheduler()
        return await self._scheduler.schedule(ScheduleRequest(
            job_name=f"reminder:{reminder.id}",
            trigger=Trigger(
                trigger_type=TriggerType.ONE_SHOT,
                run_at=reminder.remind_at,
                timezone=reminder.timezone,
            ),
            action_type="reminder",
            action_payload=self._payload(reminder),
            trace_id=reminder.trace_id,
            metadata={"tags": ["reminder"]},
        ))

    async def _ensure_job(self, reminder: Reminder):
        self._require_scheduler()
        if reminder.scheduler_job_id:
            existing = await self._scheduler.get_job(reminder.scheduler_job_id)
            if existing is not None:
                changed = await self._scheduler.reschedule_one_shot(
                    existing.info.id,
                    run_at=reminder.remind_at,
                    timezone_name=reminder.timezone,
                    action_payload=self._payload(reminder),
                )
                if changed:
                    return await self._scheduler.get_job(existing.info.id)
        return await self._create_job(reminder)

    def _failure(self, exc: Exception, operation: str, reminder: Reminder):
        if isinstance(exc, FailureException):
            source = exc.failure
            return FailureInfo(
                code=f"reminders.bridge.{operation}_failed",
                category=source.category,
                message=f"Reminder {operation} failed",
                component="reminder_bridge",
                operation=operation,
                retryable=source.retryable,
                trace_id=reminder.trace_id or source.trace_id,
                details={
                    "reminder_id": reminder.id,
                    "recovery_state": reminder.status.value,
                },
            )
        category = (
            ErrorCategory.NOT_CONFIGURED
            if isinstance(exc, ReminderUnavailableError)
            else ErrorCategory.CONFLICT
            if isinstance(exc, ReminderConflictError)
            else ErrorCategory.DEPENDENCY_FAILURE
        )
        return failure_from_exception(
            exc,
            component="reminder_bridge",
            operation=operation,
            trace_id=reminder.trace_id,
            code=f"reminders.bridge.{operation}_failed",
            category=category,
            retryable=category != ErrorCategory.CONFLICT,
            details={
                "reminder_id": reminder.id,
                "recovery_state": reminder.status.value,
            },
        ).model_copy(update={"message": f"Reminder {operation} failed"})

    async def create(
        self,
        *,
        user_task_id: str,
        remind_at: datetime,
        timezone_name: str,
        trace_id: str = "",
        metadata: dict | None = None,
    ) -> Reminder:
        reminder = await self._service.create_pending(
            user_task_id=user_task_id,
            remind_at=remind_at,
            timezone_name=timezone_name,
            trace_id=trace_id,
            metadata=metadata,
        )
        job = None
        try:
            job = await self._create_job(reminder)
            return await self._service.transition(
                reminder,
                ReminderStatus.SCHEDULED,
                scheduler_job_id=job.info.id,
                failure=None,
                trace_id=trace_id,
            )
        except Exception as exc:
            failure = self._failure(exc, "schedule", reminder)
            if job is not None:
                try:
                    await self._scheduler.cancel_job(job.info.id)
                except Exception:
                    _LOGGER.warning(
                        "reminder compensation cancel failed reminder_id=%s",
                        reminder.id,
                    )
            try:
                reminder = await self._service.transition(
                    reminder,
                    ReminderStatus.FAILED,
                    scheduler_job_id=job.info.id if job else None,
                    failure=failure,
                    trace_id=trace_id,
                )
            except Exception:
                _LOGGER.warning(
                    "reminder failure state persistence failed reminder_id=%s",
                    reminder.id,
                )
            raise FailureException(failure.model_copy(update={
                "details": {
                    "reminder_id": reminder.id,
                    "recovery_state": reminder.status.value,
                }
            })) from exc

    async def reschedule(
        self,
        reminder_id: str,
        *,
        remind_at: datetime,
        timezone_name: str,
        expected_revision: int | None,
        trace_id: str,
    ) -> Reminder:
        self._require_scheduler()
        current = await self._service.get(reminder_id, trace_id)
        if current.scheduler_job_id:
            current_job = await self._scheduler.get_job(current.scheduler_job_id)
            if current_job is not None and current_job.status == JobStatus.RUNNING:
                raise FailureException(self._failure(
                    ReminderConflictError("Running Reminder Job cannot be rescheduled"),
                    "reschedule",
                    current,
                ))
        reminder = await self._service.prepare_reschedule(
            reminder_id,
            remind_at=remind_at,
            timezone_name=timezone_name,
            expected_revision=expected_revision,
            trace_id=trace_id,
        )
        try:
            changed = False
            if reminder.scheduler_job_id:
                changed = await self._scheduler.reschedule_one_shot(
                    reminder.scheduler_job_id,
                    run_at=reminder.remind_at,
                    timezone_name=reminder.timezone,
                    action_payload=self._payload(reminder),
                )
                if not changed:
                    latest = await self._scheduler.get_job(reminder.scheduler_job_id)
                    if latest is not None:
                        raise ReminderConflictError(
                            "Reminder Job changed concurrently and cannot be rescheduled"
                        )
            if not changed:
                job = await self._create_job(reminder)
                reminder = reminder.model_copy(update={"scheduler_job_id": job.info.id})
            return await self._service.transition(
                reminder,
                ReminderStatus.SCHEDULED,
                scheduler_job_id=reminder.scheduler_job_id,
                failure=None,
                trace_id=trace_id,
            )
        except Exception as exc:
            failure = self._failure(exc, "reschedule", reminder)
            try:
                await self._service.transition(
                    reminder, ReminderStatus.PENDING_RESCHEDULE,
                    failure=failure, trace_id=trace_id,
                )
            except Exception:
                _LOGGER.warning(
                    "reminder reschedule recovery persistence failed reminder_id=%s",
                    reminder.id,
                )
            raise FailureException(failure) from exc

    async def cancel(self, reminder_id: str, trace_id: str = "") -> Reminder:
        reminder = await self._service.get(reminder_id, trace_id)
        if reminder.status == ReminderStatus.CANCELLED:
            return reminder
        if reminder.status == ReminderStatus.TRIGGERED:
            raise FailureException(self._failure(
                ReminderConflictError("Triggered Reminder cannot be cancelled"),
                "cancel",
                reminder,
            ).model_copy(update={"category": ErrorCategory.CONFLICT, "retryable": False}))
        pending = await self._service.transition(
            reminder, ReminderStatus.PENDING_CANCEL, trace_id=trace_id
        )
        try:
            if pending.scheduler_job_id and self._scheduler is not None:
                cancelled = await self._scheduler.cancel_job(pending.scheduler_job_id)
                job = await self._scheduler.get_job(pending.scheduler_job_id)
                if not cancelled and job is not None and job.status not in {
                    JobStatus.CANCELLED,
                    JobStatus.COMPLETED,
                }:
                    raise ReminderUnavailableError("Scheduler Job is currently running")
            return await self._service.transition(
                pending, ReminderStatus.CANCELLED, failure=None, trace_id=trace_id
            )
        except Exception as exc:
            failure = self._failure(exc, "cancel", pending)
            try:
                await self._service.transition(
                    pending, ReminderStatus.PENDING_CANCEL,
                    failure=failure, trace_id=trace_id,
                )
            except Exception:
                _LOGGER.warning(
                    "reminder cancel recovery persistence failed reminder_id=%s",
                    reminder.id,
                )
            raise FailureException(failure) from exc

    async def cancel_for_task(self, task_id: str, trace_id: str = "") -> None:
        reminders = await self._repository.list_for_task(task_id)
        failures = 0
        first_failed_id = ""
        for reminder in reminders:
            if reminder.status in {ReminderStatus.TRIGGERED, ReminderStatus.CANCELLED}:
                continue
            try:
                await self.cancel(reminder.id, trace_id)
            except Exception as exc:
                failures += 1
                first_failed_id = first_failed_id or reminder.id
                try:
                    current = await self._repository.get(reminder.id)
                    if current.status not in {
                        ReminderStatus.TRIGGERED,
                        ReminderStatus.CANCELLED,
                    }:
                        await self._service.transition(
                            current,
                            ReminderStatus.PENDING_CANCEL,
                            failure=self._failure(exc, "cancel", current),
                            trace_id=trace_id,
                        )
                except Exception:
                    _LOGGER.warning(
                        "task reminder recovery persistence failed reminder_id=%s",
                        reminder.id,
                    )
        if failures:
            exc = ReminderUnavailableError(
                "One or more Reminder cancellations require recovery"
            )
            failure = failure_from_exception(
                exc,
                component="reminder_bridge",
                operation="user_task_terminal",
                trace_id=trace_id,
                code="reminders.lifecycle.reconciliation_required",
                category=ErrorCategory.DEPENDENCY_FAILURE,
                retryable=True,
                details={
                    "reminder_id": first_failed_id,
                    "recovery_state": ReminderStatus.PENDING_CANCEL.value,
                },
            ).model_copy(update={"message": "Reminder lifecycle reconciliation required"})
            raise FailureException(failure) from exc

    async def reconcile(self) -> ReconciliationResult:
        result = ReconciliationResult()
        statuses = set(ReminderStatus)
        reminders = await self._repository.list_by_statuses(statuses)
        for reminder in reminders:
            try:
                task = await self._user_tasks.get(reminder.user_task_id, reminder.trace_id)
                if task.status in {UserTaskStatus.COMPLETED, UserTaskStatus.CANCELLED}:
                    if reminder.status not in {
                        ReminderStatus.TRIGGERED,
                        ReminderStatus.CANCELLED,
                    }:
                        await self.cancel(reminder.id, reminder.trace_id)
                        result.repaired += 1
                    else:
                        result.skipped += 1
                    continue

                job = (
                    await self._scheduler.get_job(reminder.scheduler_job_id)
                    if self._scheduler is not None and reminder.scheduler_job_id
                    else None
                )
                recoverable_failed = (
                    reminder.status == ReminderStatus.FAILED
                    and reminder.last_failure is not None
                    and reminder.last_failure.component == "reminder_bridge"
                )
                if (
                    reminder.status == ReminderStatus.PENDING_SCHEDULE
                    or recoverable_failed
                    or (reminder.status == ReminderStatus.SCHEDULED and job is None)
                    or (
                        reminder.status == ReminderStatus.SCHEDULED
                        and job is not None
                        and job.status in {JobStatus.FAILED, JobStatus.CANCELLED}
                    )
                ):
                    job = await self._ensure_job(reminder)
                    await self._service.transition(
                        reminder,
                        ReminderStatus.SCHEDULED,
                        scheduler_job_id=job.info.id,
                        failure=None,
                        trace_id=reminder.trace_id,
                    )
                    result.repaired += 1
                elif reminder.status == ReminderStatus.PENDING_RESCHEDULE:
                    await self.reschedule(
                        reminder.id,
                        remind_at=reminder.remind_at,
                        timezone_name=reminder.timezone,
                        expected_revision=reminder.revision,
                        trace_id=reminder.trace_id,
                    )
                    result.repaired += 1
                elif reminder.status in {
                    ReminderStatus.PENDING_CANCEL,
                    ReminderStatus.CANCELLED,
                }:
                    if reminder.status == ReminderStatus.PENDING_CANCEL:
                        await self.cancel(reminder.id, reminder.trace_id)
                        result.repaired += 1
                    elif job and job.status not in {JobStatus.CANCELLED, JobStatus.COMPLETED}:
                        await self._scheduler.cancel_job(job.info.id)
                        result.repaired += 1
                    else:
                        result.skipped += 1
                elif reminder.status == ReminderStatus.TRIGGERED:
                    if job is None:
                        job = await self._create_job(reminder)
                        await self._service.transition(
                            reminder,
                            ReminderStatus.TRIGGERED,
                            scheduler_job_id=job.info.id,
                            failure=None,
                            trace_id=reminder.trace_id,
                        )
                        result.repaired += 1
                    elif job.status != JobStatus.COMPLETED:
                        changed = await self._scheduler.reschedule_one_shot(
                            job.info.id,
                            run_at=reminder.remind_at,
                            timezone_name=reminder.timezone,
                            action_payload=self._payload(reminder),
                        )
                        if not changed:
                            raise ReminderUnavailableError(
                                "Triggered Reminder Job could not be recovered"
                            )
                        result.repaired += 1
                    else:
                        result.skipped += 1
                elif reminder.status == ReminderStatus.FAILED:
                    result.skipped += 1
                else:
                    result.skipped += 1
            except Exception:
                _LOGGER.warning(
                    "reminder reconciliation item failed reminder_id=%s",
                    reminder.id,
                )
                result.failed += 1
        self._last_reconciliation = result
        if result.failed:
            self._repository.mark_observability_degraded("reconciliation_partial_failure")
        return result

    async def health(self) -> dict[str, object]:
        if not self._initialized:
            return {"status": RuntimeStatus.NOT_INITIALIZED.value}
        if self._scheduler is None:
            return {"status": RuntimeStatus.FAILED.value, "reason": "scheduler_not_configured"}
        if self._last_reconciliation and self._last_reconciliation.failed:
            return {
                "status": RuntimeStatus.DEGRADED.value,
                "reconciliation": self._last_reconciliation.model_dump(),
            }
        return {"status": RuntimeStatus.OK.value}

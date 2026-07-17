"""Application service for natural-language Reminder creation and status views."""

from __future__ import annotations

import asyncio
import hashlib
import weakref
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from core.errors import ErrorCategory, FailureException, FailureInfo
from core.reminders.models import Reminder, ReminderOccurrenceStatus, ReminderStatus
from core.scheduler.models import JobStatus
from core.user_tasks import UserTaskPriority


class ReminderScheduleResult(BaseModel):
    task_id: str
    reminder_id: str
    scheduler_job_id: str
    task_status: str
    reminder_status: str
    scheduled_for: datetime
    timezone: str


class ReminderStatusView(BaseModel):
    status: str
    task_id: str
    task_title: str
    task_status: str
    reminder_id: str
    reminder_status: str
    scheduled_for: datetime
    timezone: str
    scheduler_job_id: str | None = None
    scheduler_status: str | None = None
    occurrence_id: str | None = None
    occurrence_status: str | None = None
    triggered_at: datetime | None = None
    last_failure: FailureInfo | None = None
    retryable: bool = False
    revision: int


def aggregate_reminder_status(reminder, job, occurrence) -> str:
    """Return the ADR-040 user-visible status shared by detail and inbox views."""
    if reminder.status == ReminderStatus.CANCELLED:
        return "cancelled"
    if reminder.status == ReminderStatus.TRIGGERED or (
        occurrence and occurrence.status == ReminderOccurrenceStatus.TRIGGERED
    ):
        return "triggered"
    if reminder.status in {
        ReminderStatus.PENDING_CANCEL,
        ReminderStatus.PENDING_RESCHEDULE,
    } and reminder.last_failure is not None:
        return "failed"
    if job and job.status == JobStatus.RETRYING:
        return "retrying"
    if reminder.status == ReminderStatus.FAILED or (job and job.status == JobStatus.FAILED):
        return "failed"
    return "scheduled"


def build_reminder_status_view(reminder, task, job, occurrence) -> ReminderStatusView:
    failure = (
        occurrence.failure if occurrence and occurrence.failure
        else reminder.last_failure
        or (job.last_error if job else None)
    )
    return ReminderStatusView(
        status=aggregate_reminder_status(reminder, job, occurrence),
        task_id=task.id,
        task_title=task.title,
        task_status=task.status.value,
        reminder_id=reminder.id,
        reminder_status=reminder.status.value,
        scheduled_for=reminder.remind_at.astimezone(ZoneInfo(reminder.timezone)),
        timezone=reminder.timezone,
        scheduler_job_id=reminder.scheduler_job_id,
        scheduler_status=job.status.value if job else None,
        occurrence_id=occurrence.id if occurrence else None,
        occurrence_status=occurrence.status.value if occurrence else None,
        triggered_at=occurrence.triggered_at if occurrence else None,
        last_failure=failure,
        retryable=failure.retryable if failure else False,
        revision=reminder.revision,
    )


class NaturalLanguageReminderOrchestrator:
    COMPONENT = "reminder.orchestration"

    def __init__(self, user_tasks, reminder_service, reminder_bridge, scheduler_runtime) -> None:
        self._user_tasks = user_tasks
        self._reminders = reminder_service
        self._bridge = reminder_bridge
        self._scheduler = scheduler_runtime
        self._idempotency_locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )

    async def create_for_task(
        self,
        *,
        title: str,
        due_at: datetime,
        timezone_name: str,
        priority: UserTaskPriority,
        description: str,
        session_id: str,
        trace_id: str,
        workspace_scope: str,
        idempotency_key: str,
        workspace: dict[str, str] | None = None,
    ) -> ReminderScheduleResult:
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        task_id = "ut_nlr_" + hashlib.sha256(
            f"{workspace_scope}|{key_hash}".encode("utf-8")
        ).hexdigest()[:24]
        lock = self._idempotency_locks.setdefault(task_id, asyncio.Lock())
        async with lock:
            return await self._create_for_task_locked(
                title=title,
                due_at=due_at,
                timezone_name=timezone_name,
                priority=priority,
                description=description,
                session_id=session_id,
                trace_id=trace_id,
                workspace_scope=workspace_scope,
                workspace=workspace or {
                    "tenant_id": "default",
                    "workspace_id": "default",
                    "namespace": "default",
                },
                idempotency_key=idempotency_key,
            )

    async def _create_for_task_locked(
        self,
        *,
        title: str,
        due_at: datetime,
        timezone_name: str,
        priority: UserTaskPriority,
        description: str,
        session_id: str,
        trace_id: str,
        workspace_scope: str,
        workspace: dict[str, str],
        idempotency_key: str,
    ) -> ReminderScheduleResult:
        key_hash = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
        intent_hash = hashlib.sha256(
            f"{workspace_scope}|{title}|{due_at.isoformat()}|{timezone_name}".encode("utf-8")
        ).hexdigest()
        task_id = "ut_nlr_" + hashlib.sha256(
            f"{workspace_scope}|{key_hash}".encode("utf-8")
        ).hexdigest()[:24]
        metadata = {
            "intent": "reminder",
            "idempotency_hash": key_hash,
            "intent_hash": intent_hash,
            "scheduling_status": "pending",
            "workspace": workspace,
        }
        try:
            task = await self._user_tasks.create(
                task_id=task_id,
                title=title,
                description=description,
                priority=priority,
                due_at=due_at,
                timezone=timezone_name,
                source="ceo_assistant",
                session_id=session_id,
                agent_id="ceo-assistant",
                trace_id=trace_id,
                metadata=metadata,
            )
        except FailureException as exc:
            if exc.failure.category != ErrorCategory.CONFLICT:
                raise
            task = await self._user_tasks.get(task_id, trace_id)
            if task.metadata.get("intent_hash") != intent_hash:
                raise FailureException(FailureInfo(
                    code="reminder.idempotency_conflict",
                    category=ErrorCategory.CONFLICT,
                    message="Idempotency key was already used for another reminder",
                    component=self.COMPONENT,
                    operation="create_natural_language_reminder",
                    retryable=False,
                    trace_id=trace_id,
                )) from exc

        reminders = await self._reminders.list_for_task(task.id, trace_id)
        reminder = self._matching_reminder(reminders, intent_hash)
        if reminder is None:
            try:
                reminder = await self._bridge.create(
                    user_task_id=task.id,
                    remind_at=due_at,
                    timezone_name=timezone_name,
                    trace_id=trace_id,
                    metadata={"intent_hash": intent_hash, "idempotency_hash": key_hash},
                )
            except FailureException as exc:
                await self._record_failure(task, exc.failure, trace_id)
                raise FailureException(FailureInfo(
                    code="reminder.scheduling_failed",
                    category=exc.failure.category,
                    message="Reminder scheduling failed",
                    component=self.COMPONENT,
                    operation="create_natural_language_reminder",
                    retryable=exc.failure.retryable,
                    trace_id=trace_id,
                    details=exc.failure.details,
                )) from exc
        elif reminder.status == ReminderStatus.FAILED:
            await self._bridge.reconcile()
            reminder = await self._reminders.get(reminder.id, trace_id)
            if reminder.status == ReminderStatus.FAILED:
                failure = reminder.last_failure or FailureInfo(
                    code="reminder.scheduling_failed",
                    category=ErrorCategory.DEPENDENCY_FAILURE,
                    message="Reminder scheduling failed",
                    component=self.COMPONENT,
                    operation="create_natural_language_reminder",
                    retryable=True,
                    trace_id=trace_id,
                )
                raise FailureException(failure)

        if not reminder.scheduler_job_id:
            raise FailureException(FailureInfo(
                code="reminder.scheduling_failed",
                category=ErrorCategory.DEPENDENCY_FAILURE,
                message="Reminder scheduling did not produce a job",
                component=self.COMPONENT,
                operation="create_natural_language_reminder",
                retryable=True,
                trace_id=trace_id,
                details={"reminder_id": reminder.id},
            ))
        task = await self._record_scheduled(task, reminder, trace_id)
        return ReminderScheduleResult(
            task_id=task.id,
            reminder_id=reminder.id,
            scheduler_job_id=reminder.scheduler_job_id,
            task_status=task.status.value,
            reminder_status=reminder.status.value,
            scheduled_for=reminder.remind_at.astimezone(ZoneInfo(reminder.timezone)),
            timezone=reminder.timezone,
        )

    async def status(self, reminder_id: str, trace_id: str = "") -> ReminderStatusView:
        reminder = await self._reminders.get(reminder_id, trace_id)
        task = await self._user_tasks.get(reminder.user_task_id, trace_id)
        job = (
            await self._scheduler.get_job(reminder.scheduler_job_id)
            if reminder.scheduler_job_id else None
        )
        occurrences = await self._reminders.list_occurrences(reminder.id, trace_id)
        occurrence = occurrences[-1] if occurrences else None
        return build_reminder_status_view(reminder, task, job, occurrence)

    @staticmethod
    def _matching_reminder(reminders: list[Reminder], intent_hash: str) -> Reminder | None:
        return next(
            (item for item in reminders if item.metadata.get("intent_hash") == intent_hash),
            None,
        )

    async def _record_scheduled(self, task, reminder: Reminder, trace_id: str):
        metadata = dict(task.metadata)
        metadata.update({
            "scheduling_status": "scheduled",
            "reminder_id": reminder.id,
            "scheduler_job_id": reminder.scheduler_job_id,
        })
        return await self._user_tasks.update(
            task.id, metadata=metadata, expected_revision=task.revision, trace_id=trace_id
        )

    async def _record_failure(self, task, failure: FailureInfo, trace_id: str) -> None:
        metadata: dict[str, Any] = dict(task.metadata)
        metadata.update({
            "scheduling_status": "failed",
            "scheduling_failure_code": failure.code,
            "reminder_id": failure.details.get("reminder_id"),
        })
        await self._user_tasks.update(
            task.id, metadata=metadata, expected_revision=task.revision, trace_id=trace_id
        )

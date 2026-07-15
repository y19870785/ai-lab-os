"""Truthful Reminder API backed by the shared SystemContainer."""

from fastapi import APIRouter, Depends, Request

from api.dependencies import get_system
from api.models import (
    ReminderCreateRequest,
    ReminderOccurrenceResponse,
    ReminderResponse,
    ReminderUpdateRequest,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.container import SystemContainer


router = APIRouter(tags=["reminders"])


def _services(system: SystemContainer):
    if system.reminder_service is None or system.reminder_bridge is None:
        raise FailureException(FailureInfo(
            code="reminders.disabled",
            category=ErrorCategory.DISABLED,
            message="Reminder service is disabled",
            component="reminders",
            operation="resolve",
        ))
    return system.reminder_service, system.reminder_bridge


def _trace(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _response(reminder) -> ReminderResponse:
    data = reminder.model_dump(exclude={"last_failure"})
    return ReminderResponse(**data)


@router.post(
    "/tasks/{task_id}/reminders",
    response_model=ReminderResponse,
    status_code=201,
)
async def create_reminder(
    task_id: str,
    body: ReminderCreateRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    _, bridge = _services(system)
    reminder = await bridge.create(
        user_task_id=task_id,
        remind_at=body.remind_at,
        timezone_name=body.timezone,
        trace_id=_trace(request),
        metadata=body.metadata,
    )
    return _response(reminder)


@router.get("/tasks/{task_id}/reminders", response_model=list[ReminderResponse])
async def list_task_reminders(
    task_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    service, _ = _services(system)
    reminders = await service.list_for_task(task_id, _trace(request))
    return [_response(reminder) for reminder in reminders]


@router.get("/reminders/{reminder_id}", response_model=ReminderResponse)
async def get_reminder(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    service, _ = _services(system)
    return _response(await service.get(reminder_id, _trace(request)))


@router.patch("/reminders/{reminder_id}", response_model=ReminderResponse)
async def reschedule_reminder(
    reminder_id: str,
    body: ReminderUpdateRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    _, bridge = _services(system)
    reminder = await bridge.reschedule(
        reminder_id,
        remind_at=body.remind_at,
        timezone_name=body.timezone,
        expected_revision=body.revision,
        trace_id=_trace(request),
    )
    return _response(reminder)


@router.delete("/reminders/{reminder_id}", response_model=ReminderResponse)
async def cancel_reminder(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    _, bridge = _services(system)
    return _response(await bridge.cancel(reminder_id, _trace(request)))


@router.get(
    "/reminders/{reminder_id}/occurrences",
    response_model=list[ReminderOccurrenceResponse],
)
async def list_reminder_occurrences(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    service, _ = _services(system)
    occurrences = await service.list_occurrences(reminder_id, _trace(request))
    return [ReminderOccurrenceResponse(**item.model_dump(exclude={"failure"})) for item in occurrences]

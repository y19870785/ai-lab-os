"""Truthful Reminder API backed by the shared SystemContainer."""

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import (
    ReminderCreateRequest,
    ReminderOccurrenceResponse,
    ReminderResponse,
    ReminderUpdateRequest,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.container import SystemContainer
from core.reminders import (
    ReminderInboxPage,
    ReminderInboxStatus,
    ReminderInboxTimeScope,
    ReminderInboxView,
    ReminderStatusView,
)
from core.workspace.models import WorkspaceKey


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


def _management(system: SystemContainer):
    if system.reminder_management is None:
        raise FailureException(FailureInfo(
            code="reminder.management_unavailable",
            category=ErrorCategory.UNAVAILABLE,
            message="Reminder management is unavailable",
            component="reminder.management",
            operation="resolve",
            retryable=False,
        ))
    return system.reminder_management


def _trace(request: Request) -> str:
    return getattr(request.state, "trace_id", "")


def _workspace(request: Request) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        trace_id=_trace(request),
    )


@router.get("/reminders", response_model=ReminderInboxPage)
async def list_reminders(
    request: Request,
    status: ReminderInboxStatus | None = None,
    time_scope: ReminderInboxTimeScope | None = None,
    view: ReminderInboxView | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    system: SystemContainer = Depends(get_system),
):
    if system.reminder_inbox is None:
        raise FailureException(FailureInfo(
            code="reminder.inbox_unavailable",
            category=ErrorCategory.UNAVAILABLE,
            message="Reminder inbox is unavailable",
            component="reminder.inbox",
            operation="list",
            retryable=False,
            trace_id=_trace(request),
        ))
    return await system.reminder_inbox.list(
        workspace_key=_workspace(request),
        statuses={status} if status else None,
        time_scope=time_scope,
        view=view,
        limit=limit,
        offset=offset,
        trace_id=_trace(request),
    )


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
    resolution = await _management(system).resolve(
        workspace_key=_workspace(request),
        reminder_id=reminder_id,
        trace_id=_trace(request),
    )
    return _response(resolution.reminder)


@router.get("/reminders/{reminder_id}/status", response_model=ReminderStatusView)
async def get_reminder_status(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    return await _management(system).status(
        workspace_key=_workspace(request),
        reminder_id=reminder_id,
        trace_id=_trace(request),
    )


@router.patch("/reminders/{reminder_id}", response_model=ReminderStatusView)
async def reschedule_reminder(
    reminder_id: str,
    body: ReminderUpdateRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    result = await _management(system).reschedule(
        workspace_key=_workspace(request),
        reminder_id=reminder_id,
        remind_at=body.target_time,
        timezone_name=body.timezone,
        expected_revision=body.revision,
        idempotency_key=request.headers.get("Idempotency-Key", ""),
        trace_id=_trace(request),
    )
    return result.current


@router.delete("/reminders/{reminder_id}", response_model=ReminderStatusView)
async def cancel_reminder(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    result = await _management(system).cancel(
        workspace_key=_workspace(request),
        reminder_id=reminder_id,
        trace_id=_trace(request),
    )
    return result.current


@router.get(
    "/reminders/{reminder_id}/occurrences",
    response_model=list[ReminderOccurrenceResponse],
)
async def list_reminder_occurrences(
    reminder_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    await _management(system).status(
        workspace_key=_workspace(request),
        reminder_id=reminder_id,
        trace_id=_trace(request),
    )
    service, _ = _services(system)
    occurrences = await service.list_occurrences(reminder_id, _trace(request))
    return [ReminderOccurrenceResponse(**item.model_dump(exclude={"failure"})) for item in occurrences]

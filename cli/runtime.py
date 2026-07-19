"""CLI 对共享 Composition Root 的薄适配层。"""

from __future__ import annotations

from applications.models import ApplicationRequest, ApplicationResponse
from core.system import create_system, load_system_settings
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.workspace.models import WorkspaceKey


async def execute_ceo_request(user_input: str) -> tuple[ApplicationResponse, str]:
    """Run one command through the same system factory used by API and interactive CLI."""

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        response = await system.application_runtime.execute(ApplicationRequest(
            application_name="ceo-assistant",
            user_input=user_input,
        ))
        return response, settings.provider_mode
    finally:
        await system.shutdown()


async def query_reminder_status(reminder_id: str):
    """Query persisted Reminder state and always close the shared system."""

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        if system.reminder_management is None:
            raise FailureException(FailureInfo(
                code="reminder.unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder status is unavailable",
                component="reminder.orchestration",
                operation="get_status",
                retryable=False,
            ))
        return await system.reminder_management.status(
            workspace_key=WorkspaceKey(), reminder_id=reminder_id
        )
    finally:
        await system.shutdown()


async def query_reminder_inbox(
    *, statuses=None, time_scope=None, view=None, limit: int = 20, offset: int = 0
):
    """Query the persisted Reminder inbox and always close the system."""
    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        if system.reminder_inbox is None:
            raise FailureException(FailureInfo(
                code="reminder.inbox_unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder inbox is unavailable",
                component="reminder.inbox",
                operation="list",
                retryable=False,
            ))
        return await system.reminder_inbox.list(
            workspace_key=WorkspaceKey(),
            statuses=statuses,
            time_scope=time_scope,
            view=view,
            limit=limit,
            offset=offset,
        )
    finally:
        await system.shutdown()


async def cancel_reminder(reminder_id: str):
    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        if system.reminder_management is None:
            raise FailureException(FailureInfo(
                code="reminder.management_unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder management is unavailable",
                component="reminder.management",
                operation="cancel",
            ))
        return await system.reminder_management.cancel(
            workspace_key=WorkspaceKey(), reminder_id=reminder_id
        )
    finally:
        await system.shutdown()


async def reschedule_reminder(
    reminder_id: str, *, scheduled_for, timezone_name: str, idempotency_key: str = ""
):
    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        if system.reminder_management is None:
            raise FailureException(FailureInfo(
                code="reminder.management_unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Reminder management is unavailable",
                component="reminder.management",
                operation="reschedule",
            ))
        return await system.reminder_management.reschedule(
            workspace_key=WorkspaceKey(),
            reminder_id=reminder_id,
            remind_at=scheduled_for,
            timezone_name=timezone_name,
            idempotency_key=idempotency_key,
        )
    finally:
        await system.shutdown()

async def query_daily_agenda(
    *, view: str = "today", window_hours=None, limit: int = 50, offset: int = 0
):
    """Query the Daily Agenda read model and always close the system."""
    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        if system.daily_agenda is None:
            raise FailureException(FailureInfo(
                code="agenda.unavailable",
                category=ErrorCategory.UNAVAILABLE,
                message="Daily agenda is unavailable",
                component="agenda.service",
                operation="list",
                retryable=False,
            ))
        return await system.daily_agenda.list(
            workspace_key=WorkspaceKey(),
            view=view,
            window_hours=window_hours,
            limit=limit,
            offset=offset,
            trace_id="cli",
        )
    finally:
        await system.shutdown()


async def execute_inbox_operation(operation: str, **values):
    """Execute one Inbox command through the shared Composition Root."""

    settings = load_system_settings()
    system = await create_system(settings)
    await system.start()
    try:
        service = system.inbox_service
        workspace_key = WorkspaceKey()
        if operation == "add":
            return await service.capture(
                workspace_key=workspace_key, source="cli", **values
            )
        if operation == "list":
            return await service.list(workspace_key=workspace_key, **values)
        if operation == "show":
            return await service.get(workspace_key=workspace_key, **values)
        if operation == "resolve-task":
            return await service.resolve_to_task(workspace_key=workspace_key, **values)
        if operation == "resolve-reminder":
            return await service.resolve_to_reminder(workspace_key=workspace_key, **values)
        if operation == "resolve-work-log":
            return await service.resolve_to_work_log(workspace_key=workspace_key, **values)
        if operation == "resolve-note":
            return await service.resolve_as_note(workspace_key=workspace_key, **values)
        if operation == "dismiss":
            return await service.dismiss(workspace_key=workspace_key, **values)
        raise ValueError(f"Unsupported Inbox operation: {operation}")
    finally:
        await system.shutdown()

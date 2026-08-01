"""Workspace-scoped Unified Inbox API."""

# ruff: noqa: B008

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import (
    InboxCaptureRequest,
    InboxItemResponse,
    InboxPageResponse,
    InboxResolveReminderRequest,
    InboxResolveTaskRequest,
    InboxResolveWaitingForRequest,
    InboxResolveWorkLogRequest,
)
from api.workspace import workspace_from_request
from core.system.container import SystemContainer

router = APIRouter(prefix="/inbox", tags=["inbox"])


def _item_response(item) -> InboxItemResponse:
    data = item.model_dump(exclude={"workspace_key"})
    return InboxItemResponse.model_validate(data)


@router.post("", response_model=InboxItemResponse, status_code=201)
async def capture_inbox_item(
    body: InboxCaptureRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.capture(
        workspace_key=workspace_from_request(request),
        content=body.content,
        source="api",
        metadata=body.metadata,
        suggested_type=body.suggested_type,
    )
    return _item_response(item)


@router.get("", response_model=InboxPageResponse)
async def list_inbox_items(
    request: Request,
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    system: SystemContainer = Depends(get_system),
):
    page = await system.inbox_service.list(
        workspace_key=workspace_from_request(request),
        status=status,
        limit=limit,
        offset=offset,
    )
    return InboxPageResponse(
        items=[_item_response(item) for item in page.items],
        status=page.status,
        limit=page.limit,
        offset=page.offset,
        has_more=page.has_more,
    )


@router.get("/{item_id}", response_model=InboxItemResponse)
async def get_inbox_item(
    item_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.get(
        workspace_key=workspace_from_request(request), inbox_item_id=item_id
    )
    return _item_response(item)


@router.post("/{item_id}/resolve/task", response_model=InboxItemResponse)
async def resolve_inbox_to_task(
    item_id: str,
    body: InboxResolveTaskRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.resolve_to_task(
        workspace_key=workspace_from_request(request),
        inbox_item_id=item_id,
        **body.model_dump(),
    )
    return _item_response(item)


@router.post("/{item_id}/resolve/reminder", response_model=InboxItemResponse)
async def resolve_inbox_to_reminder(
    item_id: str,
    body: InboxResolveReminderRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    values = body.model_dump()
    values["timezone_name"] = values.pop("timezone")
    item = await system.inbox_service.resolve_to_reminder(
        workspace_key=workspace_from_request(request),
        inbox_item_id=item_id,
        **values,
    )
    return _item_response(item)


@router.post("/{item_id}/resolve/work-log", response_model=InboxItemResponse)
async def resolve_inbox_to_work_log(
    item_id: str,
    body: InboxResolveWorkLogRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.resolve_to_work_log(
        workspace_key=workspace_from_request(request),
        inbox_item_id=item_id,
        **body.model_dump(),
    )
    return _item_response(item)


@router.post("/{item_id}/resolve/waiting-for", response_model=InboxItemResponse)
async def resolve_inbox_to_waiting_for(
    item_id: str,
    body: InboxResolveWaitingForRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.resolve_to_waiting_for(
        workspace_key=workspace_from_request(request),
        inbox_item_id=item_id,
        **body.model_dump(),
    )
    return _item_response(item)


@router.post("/{item_id}/resolve/note", response_model=InboxItemResponse)
async def resolve_inbox_as_note(
    item_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.resolve_as_note(
        workspace_key=workspace_from_request(request), inbox_item_id=item_id
    )
    return _item_response(item)


@router.post("/{item_id}/dismiss", response_model=InboxItemResponse)
async def dismiss_inbox_item(
    item_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.inbox_service.dismiss(
        workspace_key=workspace_from_request(request), inbox_item_id=item_id
    )
    return _item_response(item)

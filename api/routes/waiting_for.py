"""Workspace-scoped canonical Waiting-For API."""

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import (
    WaitingForCreateRequest,
    WaitingForCancelRequest,
    WaitingForEventPageResponse,
    WaitingForEventResponse,
    WaitingForFollowUpRequest,
    WaitingForMutationResponse,
    WaitingForPageResponse,
    WaitingForReopenRequest,
    WaitingForResolveRequest,
    WaitingForResponse,
    WaitingForSnoozeRequest,
)
from core.system.container import SystemContainer
from core.waiting_for import WaitingForView
from core.workspace.models import WorkspaceKey


router = APIRouter(prefix="/waiting-for", tags=["waiting-for"])


def _workspace(request: Request) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        trace_id=getattr(request.state, "trace_id", ""),
    )


def _item(item, *, now) -> WaitingForResponse:
    return WaitingForResponse(
        **item.model_dump(exclude={"workspace_key"}),
        review_due=item.review_due(now),
        expected_overdue=item.expected_overdue(now),
        attention_due=item.attention_due(now),
    )


def _event(event) -> WaitingForEventResponse:
    return WaitingForEventResponse.model_validate(
        event.model_dump(exclude={"workspace_key"})
    )


@router.post("", response_model=WaitingForMutationResponse, status_code=201)
async def create_waiting_for(
    body: WaitingForCreateRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    result = await system.waiting_for_service.create(
        workspace_key=_workspace(request), source="api", **body.model_dump()
    )
    return WaitingForMutationResponse(
        item=_item(result.item, now=system.clock.now()), event=_event(result.event)
    )


@router.get("", response_model=WaitingForPageResponse)
async def list_waiting_for(
    request: Request,
    view: WaitingForView = WaitingForView.OPEN,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    system: SystemContainer = Depends(get_system),
):
    page = await system.waiting_for_service.list(
        workspace_key=_workspace(request), view=view, limit=limit, offset=offset
    )
    return WaitingForPageResponse(
        items=[_item(value, now=page.generated_at) for value in page.items],
        view=page.view,
        limit=page.limit,
        offset=page.offset,
        has_more=page.has_more,
        generated_at=page.generated_at,
    )


@router.get("/{waiting_for_id}", response_model=WaitingForResponse)
async def get_waiting_for(
    waiting_for_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    item = await system.waiting_for_service.get(
        workspace_key=_workspace(request), waiting_for_id=waiting_for_id
    )
    return _item(item, now=system.clock.now())


@router.get("/{waiting_for_id}/events", response_model=WaitingForEventPageResponse)
async def list_waiting_for_events(
    waiting_for_id: str,
    request: Request,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    system: SystemContainer = Depends(get_system),
):
    page = await system.waiting_for_service.list_events(
        workspace_key=_workspace(request),
        waiting_for_id=waiting_for_id,
        limit=limit,
        offset=offset,
    )
    return WaitingForEventPageResponse(
        items=[_event(value) for value in page.items],
        limit=page.limit,
        offset=page.offset,
        has_more=page.has_more,
    )


async def _mutation(
    operation: str,
    waiting_for_id: str,
    body,
    request: Request,
    system: SystemContainer,
) -> WaitingForMutationResponse:
    values = {
        "workspace_key": _workspace(request),
        "waiting_for_id": waiting_for_id,
        "expected_revision": body.expected_revision,
        "source": "api",
    }
    if operation == "record_follow_up":
        values.update(note=body.note, next_review_at=body.next_review_at)
    elif operation == "snooze":
        values.update(note=body.note, next_review_at=body.next_review_at)
    elif operation == "resolve":
        values.update(resolution_note=body.resolution_note)
    elif operation in {"cancel", "reopen"}:
        values.update(note=body.note)
        if operation == "reopen":
            values.update(next_review_at=body.next_review_at)
    result = await getattr(system.waiting_for_service, operation)(**values)
    return WaitingForMutationResponse(
        item=_item(result.item, now=system.clock.now()), event=_event(result.event)
    )


@router.post("/{waiting_for_id}/follow-ups", response_model=WaitingForMutationResponse)
async def follow_up(waiting_for_id: str, body: WaitingForFollowUpRequest,
                    request: Request, system: SystemContainer = Depends(get_system)):
    return await _mutation("record_follow_up", waiting_for_id, body, request, system)


@router.post("/{waiting_for_id}/snooze", response_model=WaitingForMutationResponse)
async def snooze(waiting_for_id: str, body: WaitingForSnoozeRequest,
                 request: Request, system: SystemContainer = Depends(get_system)):
    return await _mutation("snooze", waiting_for_id, body, request, system)


@router.post("/{waiting_for_id}/resolve", response_model=WaitingForMutationResponse)
async def resolve(waiting_for_id: str, body: WaitingForResolveRequest,
                  request: Request, system: SystemContainer = Depends(get_system)):
    return await _mutation("resolve", waiting_for_id, body, request, system)


@router.post("/{waiting_for_id}/cancel", response_model=WaitingForMutationResponse)
async def cancel(waiting_for_id: str, body: WaitingForCancelRequest,
                 request: Request, system: SystemContainer = Depends(get_system)):
    return await _mutation("cancel", waiting_for_id, body, request, system)


@router.post("/{waiting_for_id}/reopen", response_model=WaitingForMutationResponse)
async def reopen(waiting_for_id: str, body: WaitingForReopenRequest,
                 request: Request, system: SystemContainer = Depends(get_system)):
    return await _mutation("reopen", waiting_for_id, body, request, system)

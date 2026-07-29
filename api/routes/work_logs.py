"""Typed Work Log create and query routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import WorkLogCreateRequest
from core.system.container import SystemContainer
from core.work_log import WorkLogService, WorkLogSource
from core.workspace.models import WorkspaceKey

router = APIRouter(prefix="/work-logs", tags=["work-logs"])


def _workspace(request: Request) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        session_id=getattr(request.state, "session_id", ""),
        agent_id=getattr(request.state, "agent_id", ""),
        trace_id=getattr(request.state, "trace_id", ""),
    )


def _service(
    system: SystemContainer, request: Request, operation: str
) -> WorkLogService:
    service = getattr(system, "work_log_service", None)
    if service is None:
        WorkLogService.raise_not_configured(
            operation=operation,
            trace_id=_workspace(request).trace_id,
        )
    return service


@router.post("")
async def create_work_log(
    payload: WorkLogCreateRequest,
    request: Request,
    system: Annotated[SystemContainer, Depends(get_system)],
):
    """Create through the canonical service; ``user_input`` is deprecated."""

    compatibility = (
        payload.user_input.strip()
        if isinstance(payload.user_input, str)
        else ""
    )
    subject = payload.subject
    raw_text = payload.raw_text
    if subject is None and raw_text is None and compatibility:
        subject = compatibility[:500]
        raw_text = compatibility
    record = await _service(system, request, "create").create_from_input(
        workspace_key=_workspace(request),
        subject=subject,
        raw_text=raw_text,
        occurred_at=payload.occurred_at,
        timezone=payload.timezone,
        target=payload.target,
        status=payload.status,
        tags=payload.tags,
        source=WorkLogSource.API,
        context_refs=payload.context_refs,
    )
    if payload.user_input is not None:
        return {
            "answer": (
                f"[OK] 已记录工作内容：\n\n事项: {record.subject}\n"
                f"ID: {record.id}"
            ),
            "status": "ok",
            "mode": system.settings.provider_mode,
            "trace_id": _workspace(request).trace_id,
            "latency_ms": 0.0,
            "metadata": record.model_dump(mode="json"),
        }
    return record.model_dump(mode="json")


@router.get("")
async def list_work_logs(
    request: Request,
    system: Annotated[SystemContainer, Depends(get_system)],
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    target: str | None = Query(default=None),
    tags: Annotated[list[str] | None, Query()] = None,
    status: str | None = Query(default=None),
    text: str | None = Query(default=None),
    context_ref: str | None = Query(default=None),
    limit: str | None = Query(default=None),
    offset: str | None = Query(default=None),
):
    page = await _service(system, request, "list").query_from_input(
        workspace_key=_workspace(request),
        date_from=date_from,
        date_to=date_to,
        target=target,
        tags=tags or [],
        status=status,
        text=text,
        context_ref=context_ref,
        limit=50 if limit is None else limit,
        offset=0 if offset is None else offset,
    )
    return page.model_dump(mode="json")


@router.get("/{work_log_id}")
async def get_work_log(
    work_log_id: str,
    request: Request,
    system: Annotated[SystemContainer, Depends(get_system)],
):
    record = await _service(system, request, "get").get(
        workspace_key=_workspace(request), work_log_id=work_log_id
    )
    return record.model_dump(mode="json")

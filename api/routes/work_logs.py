"""Typed Work Log create and query routes."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import WorkLogCreateRequest
from core.system.container import SystemContainer
from core.work_log import (
    WorkLogCreateCommand,
    WorkLogQuery,
    WorkLogSource,
    WorkLogStatus,
)
from core.workspace.models import WorkspaceKey

router = APIRouter(prefix="/work-logs", tags=["work-logs"])


def _workspace(request: Request) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        trace_id=getattr(request.state, "trace_id", ""),
    )


@router.post("")
async def create_work_log(
    payload: WorkLogCreateRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    """Create through the canonical service; ``user_input`` is deprecated."""

    record = await system.work_log_service.create(
        workspace_key=_workspace(request),
        command=WorkLogCreateCommand(
            subject=payload.subject,
            raw_text=payload.raw_text,
            occurred_at=payload.occurred_at,
            timezone=payload.timezone,
            target=payload.target,
            status=payload.status,
            tags=payload.tags,
            source=WorkLogSource.API,
            context_refs=payload.context_refs,
        ),
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
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    target: str | None = Query(default=None),
    tags: list[str] = Query(default=[]),
    status: WorkLogStatus | None = Query(default=None),
    text: str | None = Query(default=None),
    context_ref: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=10_000),
    system: SystemContainer = Depends(get_system),
):
    page = await system.work_log_service.list(
        workspace_key=_workspace(request),
        query=WorkLogQuery(
            date_from=date_from,
            date_to=date_to,
            target=target,
            tags=tags,
            status=status,
            text=text,
            context_ref=context_ref,
            limit=limit,
            offset=offset,
        ),
    )
    return page.model_dump(mode="json")


@router.get("/{work_log_id}")
async def get_work_log(
    work_log_id: str,
    request: Request,
    system: SystemContainer = Depends(get_system),
):
    record = await system.work_log_service.get(
        workspace_key=_workspace(request), work_log_id=work_log_id
    )
    return record.model_dump(mode="json")

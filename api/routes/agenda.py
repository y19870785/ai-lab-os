"""Daily Agenda read-only API."""

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from core.system.container import SystemContainer
from core.workspace.models import WorkspaceKey

router = APIRouter(prefix="/agenda", tags=["agenda"])


@router.get("")
async def get_agenda(
    request: Request,
    view: str = Query(default="today"),
    window_hours: int | None = Query(default=None, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    system: SystemContainer = Depends(get_system),
):
    if system.daily_agenda is None:
        from core.errors import ErrorCategory, FailureException, FailureInfo
        raise FailureException(FailureInfo(
            code="agenda.unavailable", category=ErrorCategory.UNAVAILABLE,
            message="Daily agenda is unavailable", component="agenda",
            operation="query", retryable=False,
            trace_id=getattr(request.state, "trace_id", ""),
        ))
    return (await system.daily_agenda.list(
        workspace_key=WorkspaceKey(
            tenant_id=getattr(request.state, "tenant_id", "default"),
            workspace_id=getattr(request.state, "workspace_id", "default"),
            namespace=getattr(request.state, "namespace", "default"),
            trace_id=getattr(request.state, "trace_id", ""),
        ),
        view=view, window_hours=window_hours, limit=limit, offset=offset,
        trace_id=getattr(request.state, "trace_id", ""),
    )).model_dump(mode="json")

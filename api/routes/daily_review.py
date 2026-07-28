"""Protected Daily Review API."""

from fastapi import APIRouter, Depends, Request

from api.dependencies import get_system
from core.daily_review import (
    DEFAULT_DAILY_REVIEW_LIMIT,
    DEFAULT_DAILY_REVIEW_OFFSET,
    DailyReview,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.container import SystemContainer
from core.workspace.models import WorkspaceKey

router = APIRouter(prefix="/daily-review", tags=["daily-review"])


def _workspace(request: Request) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=getattr(request.state, "tenant_id", "default"),
        workspace_id=getattr(request.state, "workspace_id", "default"),
        namespace=getattr(request.state, "namespace", "default"),
        trace_id=getattr(request.state, "trace_id", ""),
    )


def _service(system: SystemContainer, trace_id: str):
    if system.daily_review is None:
        raise FailureException(FailureInfo(
            code="daily_review.unavailable",
            category=ErrorCategory.NOT_CONFIGURED,
            message="Daily Review is not configured",
            component="daily_review",
            operation="get",
            trace_id=trace_id,
        ))
    return system.daily_review


@router.get("", response_model=DailyReview)
async def get_daily_review(
    request: Request,
    date: str,
    limit: int = DEFAULT_DAILY_REVIEW_LIMIT,
    offset: int = DEFAULT_DAILY_REVIEW_OFFSET,
    system: SystemContainer = Depends(get_system),  # noqa: B008
) -> DailyReview:
    trace_id = getattr(request.state, "trace_id", "")
    service = _service(system, trace_id)
    query = service.query_from_input(
        review_date=date,
        limit=limit,
        offset=offset,
        trace_id=trace_id,
    )
    return await service.get(
        workspace_key=_workspace(request),
        query=query,
    )

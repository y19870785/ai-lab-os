"""Protected Daily Review API."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_system
from api.models import TaskResponse
from api.task_presenter import task_response
from api.workspace import workspace_from_request
from core.daily_review import (
    DEFAULT_DAILY_REVIEW_LIMIT,
    DEFAULT_DAILY_REVIEW_OFFSET,
    ActionHint,
    DailyReview,
    build_action_hints,
)
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.container import SystemContainer

router = APIRouter(prefix="/daily-review", tags=["daily-review"])


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
        workspace_key=workspace_from_request(request),
        query=query,
    )


@router.get("/action-hints", response_model=list[ActionHint])
async def get_action_hints(
    request: Request,
    date: str,
    limit: int = DEFAULT_DAILY_REVIEW_LIMIT,
    offset: int = DEFAULT_DAILY_REVIEW_OFFSET,
    system: SystemContainer = Depends(get_system),  # noqa: B008
) -> tuple[ActionHint, ...]:
    trace_id = getattr(request.state, "trace_id", "")
    service = _service(system, trace_id)
    query = service.query_from_input(
        review_date=date,
        limit=limit,
        offset=offset,
        trace_id=trace_id,
    )
    review = await service.get(
        workspace_key=workspace_from_request(request),
        query=query,
    )
    return build_action_hints(review)


class ReviewUserTaskTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


async def _transition_user_task(
    *,
    action: str,
    task_id: str,
    body: ReviewUserTaskTransitionRequest,
    request: Request,
    system: SystemContainer,
):
    service = system.user_task_service
    if service is None:
        raise FailureException(FailureInfo(
            code="user_tasks.disabled",
            category=ErrorCategory.DISABLED,
            message="UserTask service is disabled",
            component="user_tasks",
            operation=action,
        ))
    method = service.complete if action == "complete" else service.cancel
    request_as_of = service.current_instant()
    task = await method(
        workspace_key=workspace_from_request(request),
        task_id=task_id,
        expected_revision=body.expected_revision,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    return task_response(task, service=service, request_as_of=request_as_of)


@router.post(
    "/actions/user-tasks/{task_id}/complete",
    response_model=TaskResponse,
)
async def complete_user_task_from_review(
    task_id: str,
    body: ReviewUserTaskTransitionRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),  # noqa: B008
):
    return await _transition_user_task(
        action="complete",
        task_id=task_id,
        body=body,
        request=request,
        system=system,
    )


@router.post(
    "/actions/user-tasks/{task_id}/cancel",
    response_model=TaskResponse,
)
async def cancel_user_task_from_review(
    task_id: str,
    body: ReviewUserTaskTransitionRequest,
    request: Request,
    system: SystemContainer = Depends(get_system),  # noqa: B008
):
    return await _transition_user_task(
        action="cancel",
        task_id=task_id,
        body=body,
        request=request,
        system=system,
    )

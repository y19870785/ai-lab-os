"""Persistent UserTask API; Execution Tasks remain under core.task."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from api.dependencies import get_system
from api.models import TaskCreateRequest, TaskResponse, TaskUpdateRequest
from core.errors import ErrorCategory, FailureException, FailureInfo
from core.system.container import SystemContainer
from core.user_tasks import UserTaskPriority, UserTaskStatus

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _service(system: SystemContainer):
    if system.user_task_service is None:
        raise FailureException(FailureInfo(
            code="user_tasks.disabled",
            category=ErrorCategory.DISABLED,
            message="UserTask service is disabled",
            component="user_tasks",
            operation="resolve",
        ))
    return system.user_task_service


def _response(task) -> TaskResponse:
    return TaskResponse(**task.model_dump(), overdue=task.is_overdue())


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task(req: TaskCreateRequest, request: Request,
                      system: SystemContainer = Depends(get_system)):
    task = await _service(system).create(
        **req.model_dump(), source="api",
        trace_id=getattr(request.state, "trace_id", ""),
    )
    return _response(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    status: UserTaskStatus | None = None,
    priority: UserTaskPriority | None = None,
    due_from: datetime | None = None,
    due_to: datetime | None = None,
    overdue: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    system: SystemContainer = Depends(get_system),
):
    tasks = await _service(system).list(
        trace_id=getattr(request.state, "trace_id", ""),
        status=status,
        priority=priority,
        due_from=due_from,
        due_to=due_to,
        overdue=overdue,
        limit=limit,
    )
    return [_response(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request,
                   system: SystemContainer = Depends(get_system)):
    task = await _service(system).get(task_id, getattr(request.state, "trace_id", ""))
    return _response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: str, req: TaskUpdateRequest, request: Request,
                      system: SystemContainer = Depends(get_system)):
    changes = req.model_dump(exclude_unset=True)
    if "revision" in changes:
        changes["expected_revision"] = changes.pop("revision")
    task = await _service(system).update(
        task_id, **changes,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    return _response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: str, request: Request,
                        system: SystemContainer = Depends(get_system)):
    task = await _service(system).complete(task_id, getattr(request.state, "trace_id", ""))
    return _response(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(task_id: str, request: Request,
                      system: SystemContainer = Depends(get_system)):
    task = await _service(system).cancel(task_id, getattr(request.state, "trace_id", ""))
    return _response(task)

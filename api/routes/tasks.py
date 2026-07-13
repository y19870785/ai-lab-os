"""Tasks route。"""
from fastapi import APIRouter
from api.models import TaskCreateRequest, TaskResponse
router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("", response_model=TaskResponse)
async def create_task(req: TaskCreateRequest):
    return TaskResponse(task_id="task-001", status="created")

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    return TaskResponse(task_id=task_id, status="running")

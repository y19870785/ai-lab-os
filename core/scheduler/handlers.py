"""Pluggable Scheduler action handlers."""

from __future__ import annotations

from typing import Any, Protocol

from core.scheduler.exceptions import JobStateError
from core.scheduler.models import Job, JobRun


class SchedulerActionHandler(Protocol):
    """Execute one claimed job without owning Scheduler state."""

    async def execute(self, job: Job, run: JobRun) -> Any:
        ...


class ActionHandlerRegistry:
    """Register and resolve explicit Scheduler action handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, SchedulerActionHandler] = {}

    def register(self, action_type: str, handler: SchedulerActionHandler) -> None:
        name = action_type.strip()
        if not name:
            raise ValueError("action_type must not be blank")
        if name in self._handlers:
            raise ValueError(f"Action handler already registered: {name}")
        self._handlers[name] = handler

    def unregister(self, action_type: str) -> bool:
        return self._handlers.pop(action_type, None) is not None

    def get(self, action_type: str) -> SchedulerActionHandler:
        handler = self._handlers.get(action_type)
        if handler is None:
            raise JobStateError(f"Scheduler action handler is not configured: {action_type}")
        return handler

    def exists(self, action_type: str) -> bool:
        return action_type in self._handlers


class WorkflowActionHandler:
    """Preserve the existing Workflow-backed Scheduler behavior."""

    def __init__(self, workflow_runtime) -> None:
        self._workflow_runtime = workflow_runtime

    async def execute(self, job: Job, run: JobRun) -> Any:
        if self._workflow_runtime is None:
            raise JobStateError("WorkflowRuntime is not configured")
        from core.workflow.models import WorkflowRequest

        payload = {**job.workflow_variables, **job.action_payload}
        request = WorkflowRequest(
            workflow_name=job.workflow_name,
            user_input=f"Scheduled: {job.info.name}",
            variables=payload,
            trace_id=run.trace_id,
        )
        result = await self._workflow_runtime.run(request)
        if result.status.value != "completed":
            message = "; ".join(result.errors) or "Workflow execution failed"
            raise JobStateError(message)
        return result.outputs

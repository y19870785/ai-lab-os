"""Safe UserTask response adapter shared by canonical API entrypoints."""

from __future__ import annotations

from datetime import datetime

from api.models import TaskResponse


def task_response(
    task,
    *,
    service,
    request_as_of: datetime,
    include_internal_metadata: bool = False,
) -> TaskResponse:
    """Expose one TaskResponse with an explicit metadata compatibility choice."""

    return TaskResponse(
        **task.model_dump(exclude={"legacy_source_id", "metadata"}),
        metadata=(
            task.metadata
            if include_internal_metadata
            else {
                key: value
                for key, value in task.metadata.items()
                if key != "workspace"
            }
        ),
        overdue=service.is_overdue(task, as_of=request_as_of),
    )

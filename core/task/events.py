"""Task 事件类型与发布"""

from __future__ import annotations
from typing import Any


class TaskEventTypes:
    CREATED = "task.created"
    STARTED = "task.started"
    RUNNING = "task.running"
    PAUSED = "task.paused"
    RESUMED = "task.resumed"
    WAITING = "task.waiting"
    RETRY = "task.retry"
    COMPLETED = "task.completed"
    FAILED = "task.failed"
    CANCELLED = "task.cancelled"
    DESTROYED = "task.destroyed"
    TIMEOUT = "task.timeout"


async def publish_task_event(bus, event_type: str, task_id: str = "",
                              task_name: str = "", extra: dict[str, Any] | None = None):
    if bus is None:
        return
    from core.bus.memory_events import make_memory_event
    event_data = extra or {}
    event = make_memory_event(
        event_type=event_type, memory_id=task_id or "task",
        memory_type="task", source="task.runtime",
        trace_id=str(event_data.get("trace_id", "")),
        extra={"task_name": task_name, **event_data},
    )
    await bus.publish(event.event_type, event)

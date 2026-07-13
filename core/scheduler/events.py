"""Scheduler 事件类型与发布"""

from __future__ import annotations
from typing import Any


class SchedulerEventTypes:
    CREATED = "scheduler.created"
    STARTED = "scheduler.started"
    JOB_STARTED = "scheduler.job.started"
    JOB_COMPLETED = "scheduler.job.completed"
    JOB_FAILED = "scheduler.job.failed"
    PAUSED = "scheduler.paused"
    RESUMED = "scheduler.resumed"
    DELETED = "scheduler.deleted"
    SHUTDOWN = "scheduler.shutdown"


async def publish_scheduler_event(bus, event_type: str, job_id: str = "",
                                  job_name: str = "", extra: dict[str, Any] | None = None):
    if bus is None:
        return
    from core.bus.memory_events import make_memory_event
    event = make_memory_event(
        event_type=event_type, memory_id=job_id or "scheduler",
        memory_type="scheduler", source="scheduler.runtime",
        extra={"job_name": job_name, **(extra or {})},
    )
    await bus.publish(event.event_type, event)

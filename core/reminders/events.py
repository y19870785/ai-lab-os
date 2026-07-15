"""Minimal Reminder events without task content or private metadata."""

from __future__ import annotations

from core.bus.memory_events import make_memory_event


async def publish_reminder_event(
    bus,
    event_type: str,
    *,
    reminder_id: str,
    user_task_id: str,
    status: str,
    trace_id: str = "",
    occurrence_id: str = "",
) -> None:
    if bus is None:
        return
    event = make_memory_event(
        event_type=event_type,
        memory_id=reminder_id,
        memory_type="reminder",
        source="reminders",
        trace_id=trace_id,
        extra={
            "reminder_id": reminder_id,
            "user_task_id": user_task_id,
            "occurrence_id": occurrence_id,
            "status": status,
            "component": "reminders",
        },
    )
    await bus.publish(event.event_type, event)

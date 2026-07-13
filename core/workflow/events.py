"""Workflow 事件类型与发布"""

from __future__ import annotations
from typing import Any


class WorkflowEventTypes:
    """Workflow 事件类型常量"""
    CREATED = "workflow.created"
    STARTED = "workflow.started"
    STEP_STARTED = "workflow.step.started"
    STEP_COMPLETED = "workflow.step.completed"
    STEP_FAILED = "workflow.step.failed"
    COMPLETED = "workflow.completed"
    FAILED = "workflow.failed"
    PAUSED = "workflow.paused"
    RESUMED = "workflow.resumed"
    RETRY = "workflow.retry"
    CANCELLED = "workflow.cancelled"
    CHECKPOINT = "workflow.checkpoint"


async def publish_workflow_event(bus, event_type: str, workflow_id: str,
                                 agent_id: str = "", session_id: str = "",
                                 extra: dict[str, Any] | None = None):
    """通过 EventBus 发布 Workflow 事件"""
    if bus is None:
        return
    from core.bus.memory_events import make_memory_event
    event = make_memory_event(
        event_type=event_type,
        memory_id=workflow_id,
        memory_type="workflow",
        source="workflow.runtime",
        agent_id=agent_id,
        session_id=session_id,
        extra=extra or {},
    )
    await bus.publish(event.event_type, event)

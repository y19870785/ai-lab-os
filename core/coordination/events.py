"""Multi-Agent Coordination Events.

定义 coordination 层事件类型和发布辅助函数。
所有事件通过统一的 Event Bus 发布。
"""

from __future__ import annotations
from typing import Any

from core.bus.event import Event


class CoordinationEventTypes:
    """Coordination 事件类型常量。"""
    TEAM_CREATED = "coordination.team.created"
    TEAM_DESTROYED = "coordination.team.destroyed"
    TASK_DELEGATED = "coordination.task.delegated"
    TASK_COMPLETED = "coordination.task.completed"
    TASK_FAILED = "coordination.task.failed"
    MESSAGE_SENT = "coordination.message.sent"
    MESSAGE_RECEIVED = "coordination.message.received"
    ORCHESTRATION_STARTED = "coordination.orchestration.started"
    ORCHESTRATION_COMPLETED = "coordination.orchestration.completed"
    ORCHESTRATION_FAILED = "coordination.orchestration.failed"
    AGENT_JOINED = "coordination.agent.joined"
    AGENT_LEFT = "coordination.agent.left"
    RESULT_MERGED = "coordination.result.merged"


async def publish_coordination_event(
    bus,
    event_type: str,
    source: str = "coordination",
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """通过 Event Bus 发布协作事件。"""
    if bus is None:
        return
    event = Event(
        event_type=event_type,
        source=source,
        payload=payload or {},
        metadata=metadata or {},
    )
    await bus.publish(event_type, event)

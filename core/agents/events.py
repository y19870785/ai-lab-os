"""Agent event types and publishing helpers."""
from __future__ import annotations
from typing import Any
from core.bus.memory_events import make_memory_event
class AgentEventTypes:
    CREATED = "agent.created"
    STARTED = "agent.started"
    RUNNING = "agent.running"
    COMPLETED = "agent.completed"
    DEGRADED = "agent.degraded"
    FAILED = "agent.failed"
    STOPPED = "agent.stopped"
    TOOL_CALL = "agent.tool_call"
    TOOL_RESULT = "agent.tool_result"
async def publish_agent_event(bus, event_type: str, agent_id: str, session_id: str = "", extra: dict[str, Any] | None = None):
    if not bus: return
    event_data = extra or {}
    event = make_memory_event(event_type=event_type, memory_id=agent_id, memory_type="agent", source="agent.runtime", agent_id=agent_id, session_id=session_id, trace_id=str(event_data.get("trace_id", "")), extra=event_data)
    await bus.publish(event_type, event)

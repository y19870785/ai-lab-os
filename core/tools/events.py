"""Tool event types and publishing."""
from __future__ import annotations
from typing import Any
from core.bus.memory_events import make_memory_event

class ToolEventTypes:
    REGISTERED = "tool.registered"
    EXECUTED = "tool.executed"
    FAILED = "tool.failed"
    TIMEOUT = "tool.timeout"
    DISABLED = "tool.disabled"

async def publish_tool_event(bus, event_type: str, tool_name: str, agent_id: str = "", session_id: str = "", extra: dict[str, Any] | None = None):
    if not bus: return
    event = make_memory_event(event_type=event_type, memory_id=tool_name, memory_type="tool", source="tool.runtime", agent_id=agent_id, session_id=session_id, extra=extra or {})
    await bus.publish(event_type, event)
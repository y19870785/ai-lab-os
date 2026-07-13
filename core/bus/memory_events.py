"""Memory event type definitions and standard payload helpers.

All memory operations MUST publish events through these standard types
with consistent payload and metadata structures.

Standard payload fields:
- memory_id:    str  (required) — the affected memory item ID
- memory_type:  str  (required) — "session" | "episodic" | "semantic" | "decision"
- agent_id:     str  (optional) — the agent that triggered the operation
- session_id:   str  (optional) — the session context
- trace_id:     str  (optional) — distributed trace context
- extra:        dict (optional) — operation-specific data

Standard metadata fields:
- action:       str  — "created" | "updated" | "deleted" | "accessed" | "promoted"
- source:       str  — "memory.session" | "memory.episodic" | ...
- importance:   float (optional)
"""

from __future__ import annotations

from typing import Any
from core.bus import Event


class MemoryEventTypes:
    """Standard memory event type constants."""
    CREATED = "memory.created"
    UPDATED = "memory.updated"
    DELETED = "memory.deleted"
    CONSOLIDATED = "memory.consolidated"
    FORGOTTEN = "memory.forgotten"
    ACCESSED = "memory.accessed"
    PROMOTED = "memory.promoted"


def make_memory_event(
    event_type: str,
    memory_id: str,
    memory_type: str,
    source: str,
    agent_id: str = "",
    session_id: str = "",
    trace_id: str = "",
    extra: dict[str, Any] | None = None,
) -> Event:
    """Create a standardized memory event with consistent payload + metadata.

    Args:
        event_type: One of MemoryEventTypes constants
        memory_id:  The affected memory item ID
        memory_type: The memory type string ("session"/"episodic"/"semantic"/"decision")
        source:     The publishing module ("memory.session"/"memory.episodic"/...)
        agent_id:   (optional) triggering agent
        session_id: (optional) session context
        trace_id:   (optional) distributed trace ID
        extra:      (optional) additional operation-specific data

    Returns:
        Event with standardized payload and metadata.
    """
    payload: dict[str, Any] = {
        "memory_id": memory_id,
        "memory_type": memory_type,
    }
    if agent_id:
        payload["agent_id"] = agent_id
    if session_id:
        payload["session_id"] = session_id
    if trace_id:
        payload["trace_id"] = trace_id
    if extra:
        payload.update(extra)

    metadata: dict[str, Any] = {
        "source": source,
        "action": event_type.replace("memory.", ""),
    }
    if agent_id:
        metadata["agent_id"] = agent_id
    if trace_id:
        metadata["trace_id"] = trace_id

    return Event(
        event_type=event_type,
        source=source,
        payload=payload,
        metadata=metadata,
    )

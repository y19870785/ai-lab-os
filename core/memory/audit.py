"""Memory Audit - Operation logging for all memory changes.
Records who, when, and what was changed via Message Bus events.
"""
from __future__ import annotations
import json
from typing import Any
from core.bus import Event

class MemoryAuditor:
    def __init__(self, bus=None, db_manager=None):
        self._bus = bus
        self._db = db_manager
        self._subscriptions = []
        self._log = []

    async def start(self):
        if not self._bus: return
        for evt in ["memory.created", "memory.updated", "memory.deleted",
                     "memory.accessed", "memory.promoted"]:
            handler = lambda e, ev=evt: self._record(e, ev)
            sub = await self._bus.subscribe(evt, handler)
            self._subscriptions.append(sub)

    async def stop(self):
        for sub in self._subscriptions:
            sub.cancel()
        self._subscriptions.clear()

    async def _record(self, event: Event, event_type: str):
        entry = {
            "audit_id": event.event_id,
            "memory_id": event.payload.get("memory_id", ""),
            "operation": event_type.replace("memory.", ""),
            "timestamp": event.timestamp.isoformat(),
            "agent_id": event.metadata.get("agent_id", ""),
            "trace_id": event.metadata.get("trace_id", ""),
            "details": json.dumps(event.payload),
        }
        self._log.append(entry)
        if self._db:
            conn = self._db.get_connection("audit")
            conn.execute("INSERT INTO audit_log (audit_id, memory_id, operation, timestamp, agent_id, trace_id, details) VALUES (?,?,?,?,?,?,?)",
                (entry["audit_id"], entry["memory_id"], entry["operation"],
                 entry["timestamp"], entry["agent_id"], entry["trace_id"], entry["details"]),
            )
            conn.commit()

    def get_log(self, limit=100):
        return self._log[-limit:]

    async def query(self, memory_id="", operation="", limit=100):
        if not self._db:
            return [e for e in self._log if (not memory_id or e["memory_id"] == memory_id)][-limit:]
        conn = self._db.get_connection("audit")
        q = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if memory_id: q += " AND memory_id=?"; params.append(memory_id)
        if operation: q += " AND operation=?"; params.append(operation)
        q += " ORDER BY timestamp DESC LIMIT ?"; params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]

    @property
    def log_count(self):
        return len(self._log)
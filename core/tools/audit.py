"""ToolAuditLogger — records every tool execution for audit trail."""
from __future__ import annotations
from typing import Any
from core.tools.models import ToolRequest, ToolResult, ToolInfo

class ToolAuditLogger:
    def __init__(self, bus=None):
        self._records: list[dict[str, Any]] = []
        self._bus = bus
    def record(self, info: ToolInfo, request: ToolRequest, result: ToolResult) -> None:
        entry = {
            "tool_name": info.name,
            "tool_id": info.id,
            "arguments": str(request.arguments)[:500],
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "success": result.success,
            "latency_ms": result.latency_ms,
            "error": result.error,
        }
        self._records.append(entry)
    def get_records(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._records[-limit:]
    def query(self, tool_name: str = "", agent_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        results = self._records
        if tool_name:
            results = [r for r in results if r["tool_name"] == tool_name]
        if agent_id:
            results = [r for r in results if r["agent_id"] == agent_id]
        return results[-limit:]
    @property
    def record_count(self) -> int:
        return len(self._records)
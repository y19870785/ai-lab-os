"""ToolMetrics — per-tool execution statistics."""
from __future__ import annotations
from typing import Any
from dataclasses import dataclass, field

@dataclass
class ToolStats:
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0
    total_latency_ms: float = 0.0
    @property
    def success_rate(self) -> float:
        if self.call_count == 0: return 1.0
        return self.success_count / self.call_count
    @property
    def avg_latency_ms(self) -> float:
        if self.call_count == 0: return 0.0
        return self.total_latency_ms / self.call_count

class ToolMetricsCollector:
    def __init__(self):
        self._stats: dict[str, ToolStats] = {}
    def get_or_create(self, tool_name: str) -> ToolStats:
        if tool_name not in self._stats:
            self._stats[tool_name] = ToolStats()
        return self._stats[tool_name]
    def record(self, tool_name: str, success: bool, latency_ms: float = 0.0, timeout: bool = False) -> None:
        s = self.get_or_create(tool_name)
        s.call_count += 1
        s.total_latency_ms += latency_ms
        if timeout: s.timeout_count += 1
        if success: s.success_count += 1
        else: s.failure_count += 1
    def snapshot(self) -> dict[str, Any]:
        return {name: {"call_count": s.call_count, "success_rate": s.success_rate, "avg_latency_ms": s.avg_latency_ms, "timeout_count": s.timeout_count} for name, s in self._stats.items()}
    def clear(self):
        self._stats.clear()
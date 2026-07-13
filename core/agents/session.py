"""Agent Session — per-interaction state container."""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any

@dataclass
class AgentSession:
    session_id: str = ""
    agent_id: str = ""
    variables: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    tool_call_count: int = 0
    round_count: int = 0
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    active: bool = True
    def elapsed_ms(self) -> float:
        end = self.ended_at or time.time()
        return (end - self.started_at) * 1000
    def add_tokens(self, count: int) -> None:
        self.token_count += count
    def add_tool_call(self) -> None:
        self.tool_call_count += 1
    def add_round(self) -> None:
        self.round_count += 1
    def end(self) -> None:
        self.active = False
        self.ended_at = time.time()
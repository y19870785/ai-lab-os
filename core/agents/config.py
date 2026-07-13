"""Agent configuration."""
from __future__ import annotations
from dataclasses import dataclass, field
@dataclass
class AgentConfig:
    memory_enabled: bool = True
    knowledge_enabled: bool = True
    tools_enabled: bool = True
    stream: bool = False
    temperature: float = 0.7
    top_p: float = 1.0
    max_tokens: int = 2048
    timeout: int = 60
    provider_name: str = "mock"
    model: str = ""
    max_tool_rounds: int = 5
    system_prompt: str = ""
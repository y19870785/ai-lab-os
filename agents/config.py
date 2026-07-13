"""Agent Layer 配置模型。"""

from __future__ import annotations

from pydantic import BaseModel


class AgentLayerConfig(BaseModel):
    """Agent Layer 全局配置。"""
    enabled: bool = True
    default_timeout: int = 120
    max_concurrent_runs: int = 10
    max_tokens_per_run: int = 32000
    enable_agent_protocol: bool = True

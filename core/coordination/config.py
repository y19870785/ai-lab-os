"""Coordination 配置。"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CoordinationConfig:
    """Multi-Agent Coordination 配置。"""
    max_parallel_agents: int = 5
    default_timeout: float = 300.0
    message_timeout: float = 30.0
    delegation_timeout: float = 120.0
    merge_strategy: str = "rule"  # rule | llm
    enable_broadcast: bool = True
    enable_events: bool = True
    retry_delegation: int = 2
    retry_delay: float = 1.0
    enable_audit: bool = True

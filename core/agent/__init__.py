"""Agent Runtime 抽象。提供 Agent 的注册、生命周期管理和调度执行。

使用方式：
    from core.agent import AgentRuntime, AgentSpec, AgentInstance, AgentStatus

    agent_id = await runtime.register(AgentSpec(name="analyst", version="1.0"))
    await runtime.start(agent_id)
"""

import warnings

warnings.warn(
    "The 'core.agent' namespace is deprecated. New code must use 'core.agents'. "
    "The legacy types have no one-to-one canonical mapping, so their original "
    "semantics are retained through at least v0.36 and removal is no earlier "
    "than v0.37.0.",
    DeprecationWarning,
    stacklevel=2,
)

from core.agent.models import AgentFilter, AgentInstance, AgentSpec, AgentStatus
from core.agent.protocol import AgentRuntime

__all__ = [
    "AgentFilter",
    "AgentInstance",
    "AgentRuntime",
    "AgentSpec",
    "AgentStatus",
]

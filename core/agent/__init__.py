"""Agent Runtime 抽象。提供 Agent 的注册、生命周期管理和调度执行。

使用方式：
    from core.agent import AgentRuntime, AgentSpec, AgentInstance, AgentStatus

    agent_id = await runtime.register(AgentSpec(name="analyst", version="1.0"))
    await runtime.start(agent_id)
"""

from core.agent.protocol import AgentRuntime
from core.agent.models import AgentSpec, AgentInstance, AgentStatus, AgentFilter

__all__ = [
    "AgentRuntime",
    "AgentSpec",
    "AgentInstance",
    "AgentStatus",
    "AgentFilter",
]

"""Agent Layer.

AI-Lab's Agent Runtime — lifecycle, context building, LLM invocation,
tool execution, memory and knowledge integration.
"""

from core.agents.models import (
    AgentInfo, AgentRequest, AgentResponse, AgentContext,
    AgentStatus, ToolCallRecord,
)
from core.agents.protocol import AgentRuntime
from core.agents.runtime import DefaultAgentRuntime
from core.agents.lifecycle import AgentLifecycleManager, VALID_TRANSITIONS
from core.agents.registry import AgentRegistry
from core.agents.executor import AgentExecutor
from core.agents.context import ContextBuilder
from core.agents.session import AgentSession
from core.agents.config import AgentConfig
from core.agents.events import AgentEventTypes, publish_agent_event
from core.agents.exceptions import (
    AgentError, AgentInitializationError, AgentExecutionError,
    ToolExecutionError, ContextBuildError, AgentNotFoundError, AgentNotReadyError,
)

__all__ = [
    "AgentInfo", "AgentRequest", "AgentResponse", "AgentContext",
    "AgentStatus", "ToolCallRecord",
    "AgentRuntime", "DefaultAgentRuntime",
    "AgentLifecycleManager", "VALID_TRANSITIONS",
    "AgentRegistry", "AgentExecutor", "ContextBuilder", "AgentSession",
    "AgentConfig", "AgentEventTypes", "publish_agent_event",
    "AgentError", "AgentInitializationError", "AgentExecutionError",
    "ToolExecutionError", "ContextBuildError", "AgentNotFoundError", "AgentNotReadyError",
]

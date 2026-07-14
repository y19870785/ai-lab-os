"""DefaultAgentRuntime — the main Agent Runtime implementation.

Orchestrates: session -> memory -> knowledge -> context -> LLM -> tools -> memory save -> response.
Does NOT contain business logic. Delegates to Executor for the actual run cycle.
"""

from __future__ import annotations

from typing import Any

from core.agents.models import AgentRequest, AgentResponse, AgentInfo, AgentContext
from core.agents.protocol import AgentRuntime
from core.agents.lifecycle import AgentLifecycleManager, AgentStatus
from core.agents.executor import AgentExecutor
from core.agents.config import AgentConfig


class DefaultAgentRuntime(AgentRuntime):
    """Default runtime implementation."""

    def __init__(self, info: AgentInfo, llm_provider=None, memory_manager=None,
                 knowledge_manager=None, tool_registry=None, tool_executor=None,
                 config: AgentConfig | None = None, bus=None):
        self._info = info
        self._config = config or AgentConfig()
        self._llm = llm_provider
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._tools = tool_registry
        self._bus = bus
        self._lifecycle = AgentLifecycleManager(info)
        self._executor = AgentExecutor(
            info=info, llm_provider=llm_provider, memory_manager=memory_manager,
            knowledge_manager=knowledge_manager, tool_registry=tool_registry,
            tool_executor=tool_executor,
            config=self._config, bus=bus,
        )

    async def initialize(self) -> None:
        self._lifecycle.transition(AgentStatus.INITIALIZED)
        self._lifecycle.transition(AgentStatus.READY)

    async def shutdown(self) -> None:
        if self._lifecycle.current() not in (AgentStatus.DESTROYED, AgentStatus.STOPPED):
            self._lifecycle.transition(AgentStatus.STOPPED)
        self._lifecycle.transition(AgentStatus.DESTROYED)

    async def run(self, request: AgentRequest) -> AgentResponse:
        self._lifecycle.assert_runnable()
        self._lifecycle.transition(AgentStatus.RUNNING)
        try:
            response = await self._executor.execute(request)
            self._lifecycle.transition(AgentStatus.IDLE)
            return response
        except Exception:
            self._lifecycle.transition(AgentStatus.ERROR)
            raise

    async def build_context(self, request: AgentRequest) -> AgentContext:
        return await self._executor._context_builder.build(request)

    async def invoke_llm(self, context: AgentContext) -> str:
        return await self._executor._invoke_llm(context)

    async def invoke_tools(self, tool_names: list[str], context: AgentContext) -> dict[str, Any]:
        return {}

    async def after_response(self, request: AgentRequest, response: AgentResponse) -> None:
        pass

    @property
    def info(self) -> AgentInfo:
        return self._info

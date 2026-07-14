"""AgentExecutor — runs a single agent interaction cycle."""
from __future__ import annotations
import time
from typing import Any
from core.agents.models import AgentRequest, AgentResponse, AgentContext, AgentInfo, ToolCallRecord
from core.tools.models import ToolRequest
from core.agents.session import AgentSession
from core.agents.context import ContextBuilder
from core.agents.lifecycle import AgentLifecycleManager
from core.agents.config import AgentConfig
from core.agents.events import publish_agent_event, AgentEventTypes
from core.agents.exceptions import AgentExecutionError, ToolExecutionError


class AgentExecutor:
    def __init__(self, info: AgentInfo, llm_provider=None, memory_manager=None,
                 knowledge_manager=None, tool_registry=None, tool_executor=None,
                 config: AgentConfig | None = None, bus=None):
        self._info = info
        self._llm = llm_provider
        self._memory = memory_manager
        self._knowledge = knowledge_manager
        self._tools = tool_registry
        self._tool_executor = tool_executor
        self._config = config or AgentConfig()
        self._bus = bus
        self._lifecycle = AgentLifecycleManager(info)
        self._context_builder = ContextBuilder(info, self._config)

    async def execute(self, request: AgentRequest) -> AgentResponse:
        import uuid
        t0 = time.time()
        session = AgentSession(
            session_id=request.session_id or uuid.uuid4().hex[:12],
            agent_id=self._info.id,
        )
        if self._bus:
            await publish_agent_event(self._bus, AgentEventTypes.STARTED,
                                      self._info.id, session.session_id)

        try:
            memory_items = await self._fetch_memory(request) if request.memory_enabled and self._memory else []
            knowledge_results = await self._fetch_knowledge(request) if request.knowledge_enabled and self._knowledge else []
            context = await self._context_builder.build(request, memory_items, knowledge_results)
            answer = await self._invoke_llm(context)
            tools = []
            if request.tools_enabled and self._tools:
                tools = await self._invoke_tools(request, context)

            response = AgentResponse(
                answer=answer, tool_calls=tools,
                session_id=session.session_id, agent_id=self._info.id,
                latency_ms=(time.time() - t0) * 1000, status="ok",
            )
            if self._memory:
                await self._save_memory(request, response)
            if self._bus:
                await publish_agent_event(self._bus, AgentEventTypes.COMPLETED,
                                          self._info.id, session.session_id,
                                          {"latency_ms": response.latency_ms})
            return response
        except Exception as e:
            if self._bus:
                await publish_agent_event(self._bus, AgentEventTypes.FAILED,
                                          self._info.id, session.session_id,
                                          {"error": str(e)})
            return AgentResponse(
                answer=f"Error: {e}", session_id=session.session_id,
                agent_id=self._info.id, latency_ms=(time.time() - t0) * 1000,
                status="error",
            )
        finally:
            session.end()

    async def _fetch_memory(self, request: AgentRequest) -> list[dict[str, Any]]:
        if self._memory is None:
            raise AgentExecutionError("MemoryManager is not configured")
        from core.memory.models import MemoryQuery
        results = await self._memory.retrieve(MemoryQuery(top_k=5))
        return [{"content": r.content.get("summary", str(r.content))} for r in results]

    async def _fetch_knowledge(self, request: AgentRequest) -> list[dict[str, Any]]:
        from core.knowledge.models import KnowledgeQuery
        results = await self._knowledge.search(KnowledgeQuery(text=request.user_input, top_k=3))
        return [{"content": r.item.content, "score": r.score} for r in results]

    async def _invoke_llm(self, context: AgentContext) -> str:
        if self._llm is None:
            raise AgentExecutionError("LLM provider is not configured")
        from core.providers.llm.protocol import LLMRequest, Message
        msgs = [Message(role=m["role"], content=m["content"]) for m in context.messages]
        resp = await self._llm.generate(LLMRequest(
            messages=msgs, temperature=self._config.temperature,
            max_tokens=self._config.max_tokens,
        ))
        return resp.content

    async def _invoke_tools(self, request: AgentRequest, context: AgentContext) -> list[ToolCallRecord]:
        # Route tool calls through ToolExecutor -- Agent never knows about MCP.
        if self._tool_executor is None:
            raise ToolExecutionError("ToolExecutor is not configured")

        records = []
        tool_calls = context.variables.get('tool_calls', [])
        if not tool_calls:
            return records

        for tc in tool_calls:
            tool_req = ToolRequest(
                tool_name=tc.get('name', ''),
                arguments=tc.get('arguments', {}),
                agent_id=self._info.id,
                session_id=request.session_id,
                trace_id=request.trace_id or '',
            )
            result = await self._tool_executor.execute(tool_req)
            records.append(ToolCallRecord(
                tool_name=tc.get('name', ''),
                arguments=tc.get('arguments', {}),
                result=str(result.output) if result.success else str(result.error),
                success=result.success,
            ))

        return records

    async def _save_memory(self, request: AgentRequest, response: AgentResponse) -> None:
        if self._memory is None:
            raise AgentExecutionError("MemoryManager is not configured")
        from core.memory.models import MemoryItem, MemoryType
        item = MemoryItem(
            memory_type=MemoryType.EPISODIC,
            content={
                "request": request.user_input,
                "response": response.answer[:500],
                "session_id": request.session_id,
            },
            importance=0.5,
        )
        await self._memory.save(item)

"""AgentExecutor — runs a single agent interaction cycle."""
from __future__ import annotations
import logging
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
from core.errors import (
    ErrorCategory,
    ErrorSeverity,
    FailureException,
    FailureInfo,
    failure_event_payload,
    failure_from_exception,
)


logger = logging.getLogger("ai-lab.agents.executor")


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
        trace_id = request.trace_id or session.session_id
        if self._bus:
            await publish_agent_event(self._bus, AgentEventTypes.STARTED,
                                      self._info.id, session.session_id)

        operation = "dependencies.validate"
        try:
            self._validate_requested_dependencies(request, trace_id)
            operation = "memory.retrieve"
            memory_items = await self._fetch_memory(request) if request.memory_enabled else []
            operation = "knowledge.retrieve"
            knowledge_results = await self._fetch_knowledge(request) if request.knowledge_enabled else []
            operation = "context.build"
            context = await self._context_builder.build(request, memory_items, knowledge_results)
            operation = "provider.generate"
            answer = await self._invoke_llm(context)
            tools = []
            if request.tools_enabled:
                operation = "tool.execute"
                tools = await self._invoke_tools(request, context)
                failed_tool = next((record for record in tools if not record.success), None)
                if failed_tool is not None:
                    raise ToolExecutionError(
                        failed_tool.error or f"Tool {failed_tool.tool_name} failed"
                    )

            response = AgentResponse(
                answer=answer, tool_calls=tools,
                session_id=session.session_id, agent_id=self._info.id,
                latency_ms=(time.time() - t0) * 1000, status="ok",
                trace_id=trace_id,
            )
            if request.memory_enabled:
                try:
                    await self._save_memory(request, response)
                except Exception as exc:
                    failure = failure_from_exception(
                        exc,
                        component="agent.memory",
                        operation="save",
                        trace_id=trace_id,
                        code="agent.memory.save_failed",
                        category=ErrorCategory.PERSISTENCE_FAILURE,
                        retryable=True,
                        severity=ErrorSeverity.WARNING,
                    )
                    response.status = "degraded"
                    response.failure = failure
                    response.retryable = failure.retryable
                    response.metadata["memory_saved"] = False
                    if hasattr(self._memory, "record_failure"):
                        self._memory.record_failure(failure)
                    if self._bus:
                        await publish_agent_event(
                            self._bus,
                            AgentEventTypes.DEGRADED,
                            self._info.id,
                            session.session_id,
                            failure_event_payload(failure, status="degraded"),
                        )
                    return response
            if self._bus:
                await publish_agent_event(self._bus, AgentEventTypes.COMPLETED,
                                          self._info.id, session.session_id,
                                          {"status": "ok", "trace_id": trace_id,
                                           "latency_ms": response.latency_ms})
            return response
        except Exception as exc:
            component, action = operation.split(".", 1)
            failure = failure_from_exception(
                exc,
                component=f"agent.{component}",
                operation=action,
                trace_id=trace_id,
                code=f"agent.{operation}_failed",
            )
            if failure.category == ErrorCategory.INTERNAL and component in {
                "memory", "knowledge", "provider", "tool"
            }:
                failure = failure.model_copy(update={
                    "category": ErrorCategory.DEPENDENCY_FAILURE,
                    "retryable": component != "tool",
                })
            if component == "memory" and hasattr(self._memory, "record_failure"):
                self._memory.record_failure(failure)
            logger.exception(
                "agent.execution.failed",
                extra={"component": failure.component, "operation": failure.operation,
                       "trace_id": trace_id, "failure_code": failure.code},
            )
            if self._bus:
                await publish_agent_event(self._bus, AgentEventTypes.FAILED,
                                          self._info.id, session.session_id,
                                          failure_event_payload(failure))
            return AgentResponse(
                answer="", session_id=session.session_id,
                agent_id=self._info.id, latency_ms=(time.time() - t0) * 1000,
                status="failed", trace_id=trace_id,
                retryable=failure.retryable, failure=failure,
            )
        finally:
            session.end()

    def _validate_requested_dependencies(self, request: AgentRequest, trace_id: str) -> None:
        memory_not_configured = self._memory is None
        if request.memory_enabled and self._memory is not None and hasattr(self._memory, "health"):
            memory_not_configured = (
                self._memory.health().get("status") == ErrorCategory.NOT_CONFIGURED.value
            )
        requirements = (
            (request.memory_enabled and memory_not_configured,
             "agent.memory.not_configured", "agent.memory", "retrieve",
             "Memory service is not configured", ErrorCategory.NOT_CONFIGURED),
            (request.knowledge_enabled and not self._config.knowledge_enabled,
             "agent.knowledge.disabled", "agent.knowledge", "retrieve",
             "Knowledge service is disabled", ErrorCategory.DISABLED),
            (request.knowledge_enabled and self._config.knowledge_enabled and self._knowledge is None,
             "agent.knowledge.not_configured", "agent.knowledge", "retrieve",
             "Knowledge service is not configured", ErrorCategory.NOT_CONFIGURED),
            (request.tools_enabled and (self._tools is None or self._tool_executor is None),
             "agent.tool.not_configured", "agent.tool", "execute",
             "Tool runtime is not configured", ErrorCategory.NOT_CONFIGURED),
        )
        for missing, code, component, action, message, category in requirements:
            if missing:
                raise FailureException(FailureInfo(
                    code=code,
                    category=category,
                    message=message,
                    component=component,
                    operation=action,
                    trace_id=trace_id,
                ))

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
                error=None if result.success else str(result.error),
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

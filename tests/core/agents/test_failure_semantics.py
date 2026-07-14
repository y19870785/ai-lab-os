import pytest

from core.agents import AgentExecutor, AgentInfo, AgentRequest, DefaultAgentRuntime
from core.agents.models import AgentContext, AgentStatus
from core.bus.bus import MemoryBus
from core.errors import ErrorCategory
from core.providers.llm.mock import MockLLMProvider


pytestmark = pytest.mark.asyncio(loop_scope="function")


class BrokenProvider:
    async def generate(self, request):
        raise ConnectionError("provider unavailable")


class BrokenRetrieveMemory:
    async def retrieve(self, query):
        raise RuntimeError("memory read failed")


class BrokenSaveMemory:
    async def retrieve(self, query):
        return []

    async def save(self, item):
        raise OSError("memory database unavailable")


class BrokenKnowledge:
    async def search(self, query):
        raise RuntimeError("vector search failed")


class BrokenToolExecutor:
    async def execute(self, request):
        raise RuntimeError("tool process failed")


async def _mock_llm():
    provider = MockLLMProvider()
    await provider.initialize()
    return provider


async def test_provider_failure_is_structured_and_runtime_enters_error():
    runtime = DefaultAgentRuntime(AgentInfo(id="agent-1"), llm_provider=BrokenProvider())
    await runtime.initialize()

    response = await runtime.run(AgentRequest(
        user_input="hello",
        memory_enabled=False,
        knowledge_enabled=False,
        tools_enabled=False,
        trace_id="agent-trace",
    ))

    assert response.status == "failed"
    assert response.answer == ""
    assert response.failure is not None
    assert response.failure.code == "agent.provider.generate_failed"
    assert response.failure.category == ErrorCategory.UNAVAILABLE
    assert response.trace_id == "agent-trace"
    assert runtime.info.status == AgentStatus.ERROR


@pytest.mark.parametrize(
    ("agent_request", "expected_code"),
    [
        (AgentRequest(user_input="x", memory_enabled=True,
                      knowledge_enabled=False, tools_enabled=False),
         "agent.memory.not_configured"),
        (AgentRequest(user_input="x", memory_enabled=False,
                      knowledge_enabled=True, tools_enabled=False),
         "agent.knowledge.not_configured"),
        (AgentRequest(user_input="x", memory_enabled=False,
                      knowledge_enabled=False, tools_enabled=True),
         "agent.tool.not_configured"),
    ],
)
async def test_enabled_capability_without_dependency_fails(agent_request, expected_code):
    response = await AgentExecutor(
        AgentInfo(id="missing-dependency-agent"),
        llm_provider=await _mock_llm(),
    ).execute(agent_request)

    assert response.status == "failed"
    assert response.answer == ""
    assert response.failure is not None
    assert response.failure.code == expected_code
    assert response.failure.category == ErrorCategory.NOT_CONFIGURED


async def test_explicitly_disabled_capabilities_may_be_skipped():
    response = await AgentExecutor(
        AgentInfo(id="disabled-capabilities-agent"),
        llm_provider=await _mock_llm(),
    ).execute(AgentRequest(
        user_input="x",
        memory_enabled=False,
        knowledge_enabled=False,
        tools_enabled=False,
    ))

    assert response.status == "ok"
    assert response.failure is None


async def test_memory_retrieve_and_knowledge_failures_have_distinct_codes():
    llm = await _mock_llm()
    memory_response = await AgentExecutor(
        AgentInfo(id="memory-agent"),
        llm_provider=llm,
        memory_manager=BrokenRetrieveMemory(),
    ).execute(AgentRequest(user_input="x", knowledge_enabled=False, tools_enabled=False))
    knowledge_response = await AgentExecutor(
        AgentInfo(id="knowledge-agent"),
        llm_provider=llm,
        knowledge_manager=BrokenKnowledge(),
    ).execute(AgentRequest(user_input="x", memory_enabled=False, tools_enabled=False))

    assert memory_response.failure.code == "agent.memory.retrieve_failed"
    assert knowledge_response.failure.code == "agent.knowledge.retrieve_failed"
    assert memory_response.answer == knowledge_response.answer == ""


async def test_memory_save_failure_preserves_answer_and_marks_runtime_degraded():
    runtime = DefaultAgentRuntime(
        AgentInfo(id="agent-2"),
        llm_provider=await _mock_llm(),
        memory_manager=BrokenSaveMemory(),
    )
    await runtime.initialize()

    response = await runtime.run(AgentRequest(
        user_input="remember this",
        knowledge_enabled=False,
        tools_enabled=False,
    ))

    assert response.answer
    assert response.status == "degraded"
    assert response.failure.code == "agent.memory.save_failed"
    assert response.failure.category == ErrorCategory.PERSISTENCE_FAILURE
    assert runtime.info.status == AgentStatus.DEGRADED


async def test_tool_executor_failure_is_not_reported_as_ok(monkeypatch):
    executor = AgentExecutor(
        AgentInfo(id="tool-agent"),
        llm_provider=await _mock_llm(),
        tool_registry=object(),
        tool_executor=BrokenToolExecutor(),
    )

    async def build_context(*args, **kwargs):
        return AgentContext(
            messages=[{"role": "user", "content": "run tool"}],
            variables={"tool_calls": [{"name": "broken", "arguments": {}}]},
        )

    monkeypatch.setattr(executor._context_builder, "build", build_context)
    response = await executor.execute(AgentRequest(
        user_input="run tool",
        memory_enabled=False,
        knowledge_enabled=False,
    ))

    assert response.status == "failed"
    assert response.failure.code == "agent.tool.execute_failed"
    assert response.answer == ""


async def test_agent_failed_event_uses_common_envelope():
    bus = MemoryBus()
    events = []

    async def collect(event):
        events.append(event)

    await bus.start()
    await bus.subscribe("agent.failed", collect)
    try:
        executor = AgentExecutor(AgentInfo(id="event-agent"), llm_provider=BrokenProvider(), bus=bus)
        await executor.execute(AgentRequest(
            user_input="x",
            memory_enabled=False,
            knowledge_enabled=False,
            tools_enabled=False,
            trace_id="event-trace",
        ))
    finally:
        await bus.stop()

    assert len(events) == 1
    assert events[0].payload["code"] == "agent.provider.generate_failed"
    assert events[0].payload["category"] == "unavailable"
    assert events[0].payload["trace_id"] == "event-trace"

"""Enterprise Assistant End-to-End Demo.

完整闭环演示:
Scheduler -> Task -> Workflow -> Agent -> Knowledge -> Tool -> Memory -> Response

使用 Mock Providers，可无 API key 运行。
"""

import asyncio
import sys
sys.path.insert(0, ".")

from core.agents.models import AgentRequest, AgentInfo
from core.agents.runtime import DefaultAgentRuntime
from core.agents.config import AgentConfig
from core.providers.llm.mock import MockLLMProvider
from core.memory.manager import MemoryManager
from core.knowledge.ingestion import IngestionPipeline
from core.knowledge.models import KnowledgeQuery, SourceType, KnowledgeType
from core.knowledge.manager import KnowledgeManager
from core.tools.registry import ToolRegistry
from core.tools.builtin.echo import EchoTool
from core.tools.builtin.calculator import CalculatorTool
from core.tools.executor import ToolExecutor


async def main():
    print("=" * 60)
    print("Enterprise Assistant End-to-End Demo")
    print("=" * 60)

    # 1. Initialize Providers
    print("\n[1/6] Initializing providers...")
    llm = MockLLMProvider()
    await llm.initialize()
    memory = MemoryManager()
    print("  [OK] LLM + Memory ready")

    # 2. Setup Knowledge
    print("\n[2/6] Loading knowledge base...")
    knowledge = KnowledgeManager()
    pipe = IngestionPipeline()
    docs = [
        "AI-Lab supports multi-agent coordination and task planning.",
        "Enterprise users can deploy custom AI agents for specific workflows.",
        "The system is built with Provider Layer for model-agnostic architecture.",
    ]
    for i, doc in enumerate(docs):
        item, chunks = await pipe.ingest(
            content=doc, title=f"Knowledge {i}", source=f"kb{i}.txt",
            source_type=SourceType.PLAINTEXT, knowledge_type=KnowledgeType.DOCUMENT,
        )
        await knowledge.save(item)
    print(f"  [OK] {len(docs)} documents indexed")

    # 3. Setup Tools
    print("\n[3/6] Registering tools...")
    registry = ToolRegistry()
    for tool in [EchoTool(), CalculatorTool()]:
        registry.register(tool.info, tool.__class__)
    print(f"  [OK] {len(registry.list_names())} tools registered")

    # 4. Setup Agent
    print("\n[4/6] Creating agent...")
    info = AgentInfo(name="enterprise-assistant", description="Enterprise AI assistant")
    config = AgentConfig(memory_enabled=True, knowledge_enabled=True, tools_enabled=True)
    runtime = DefaultAgentRuntime(
        info=info, llm_provider=llm, memory_manager=memory,
        knowledge_manager=knowledge, tool_registry=registry, config=config,
    )
    await runtime.initialize()
    print(f"  [OK] Agent '{info.name}' ready ({info.id[:8]}...)")

    # 5. Conversation Loop
    print("\n[5/6] Starting conversation...")
    queries = [
        "What can you tell me about AI-Lab?",
        "Calculate 100 + 200 for me.",
        "Echo: Hello from enterprise demo!",
        "What is the system architecture?",
    ]
    for i, q in enumerate(queries):
        print(f"\n  User [{i+1}]: {q}")
        req = AgentRequest(
            user_input=q, session_id="demo-session",
            agent_id=info.id,
            memory_enabled=True, knowledge_enabled=True, tools_enabled=True,
        )
        resp = await runtime.run(req)
        print(f"  Agent: {resp.answer[:200]}")
        print(f"  [Latency: {resp.latency_ms:.0f}ms, Tokens: {resp.usage.get('total_tokens', 'N/A')}]")

    # 6. Shutdown
    print("\n[6/6] Shutting down...")
    await runtime.shutdown()
    await llm.shutdown()
    print("  [OK] All resources released")

    print("\n" + "=" * 60)
    print("End-to-End Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

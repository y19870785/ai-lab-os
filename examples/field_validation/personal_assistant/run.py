"""Personal Assistant Demo —— 多轮对话 + Memory + Knowledge。

Usage:
    python examples/field_validation/personal_assistant/run.py
"""
import asyncio
import sys
import os
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))


async def main():
    print("=" * 60)
    print("Field Validation: Personal Assistant Demo")
    print("=" * 60)

    from core.providers.llm.mock import MockLLMProvider
    from core.providers.llm.openai import OpenAILLMProvider
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.session import SessionMemory
    from core.agents.models import AgentInfo, AgentRequest
    from core.agents.runtime import DefaultAgentRuntime
    from core.agents.config import AgentConfig

    # Setup
    data_dir = os.path.join(os.getcwd(), "data", "sqlite")
    os.makedirs(data_dir, exist_ok=True)

    # Choose provider: real if API key set, else mock
    api_key = os.getenv("OPENAI_API_KEY", "")
    provider_name = "REAL" if api_key else "MOCK"

    if api_key:
        llm = OpenAILLMProvider(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", ""),
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
        )
    else:
        api_key = os.getenv("OPENAI_API_KEY") or ""
        base_url = os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1"

        if api_key:
            llm = OpenAILLMProvider(api_key=api_key, base_url=base_url)
        else:
            llm = MockLLMProvider()

    await llm.initialize()

    memory = MemoryManager()
    sm = SessionMemory(default_ttl=3600)
    memory.register_store(MemoryType.SESSION, sm)
    es = SQLiteEpisodicStore(db_path=os.path.join(data_dir, "demo_episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)

    info = AgentInfo(id="personal-assistant-001", name="personal-assistant", description="Your personal AI assistant")
    config = AgentConfig(memory_enabled=True, knowledge_enabled=True)
    runtime = DefaultAgentRuntime(info=info, llm_provider=llm, memory_manager=memory, config=config)
    await runtime.initialize()

    print(f"\nProvider mode: {provider_name} ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})\n")

    # Multi-turn conversation
    session_id = "demo-session-001"
    questions = [
        "你好！用中文回复。你能帮我做什么？",
        "告诉我你的记忆系统是怎么工作的？",
        "我刚才问了你什么问题？",
    ]

    for i, q in enumerate(questions):
        req = AgentRequest(
            user_input=q, session_id=session_id,
            agent_id=info.id, memory_enabled=True,
        )
        resp = await runtime.run(req)
        print(f"[Turn {i+1}] Q: {q}")
        answer = resp.answer
        print(f"          A: {answer[:200]}{'...' if len(answer) > 200 else ''}")
        print(f"          ({resp.latency_ms:.0f}ms | trace: {resp.agent_id[:8]})\n")

    # Verify memory saved
    print("--- Memory Check ---")
    memory_count = await es.count()
    print(f"Episodic memories saved: {memory_count}")

    await runtime.shutdown()
    await llm.shutdown()
    await es.close()
    print(f"\nPersonal Assistant Demo Complete [{provider_name} mode]")


if __name__ == "__main__":
    asyncio.run(main())

"""AI-Lab CLI —— 多轮对话命令。"""
import asyncio, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

async def run(args):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    user_input = " ".join(args) if args else "Hello"

    from applications.ceo_assistant.application import CEOAssistant
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from core.memory.session import SessionMemory
    from core.bus.bus import get_bus

    data_dir = os.path.join(os.getcwd(), "data", "sqlite")
    os.makedirs(data_dir, exist_ok=True)

    bus = get_bus(); await bus.start()
    memory = MemoryManager(bus=bus)
    memory.register_store(MemoryType.SESSION, SessionMemory(default_ttl=3600, bus=bus))
    es = SQLiteEpisodicStore(db_path=os.path.join(data_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)
    ds = SQLiteDecisionStore(db_path=os.path.join(data_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    # Try real LLM if available
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "")
    llm = None
    if api_key:
        from core.providers.llm.openai import OpenAILLMProvider
        llm = OpenAILLMProvider(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", ""),
            model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
        )
        await llm.initialize()

    app = CEOAssistant(memory_manager=memory, llm_provider=llm)
    from applications.models import ApplicationRequest
    resp = await app.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input=user_input,
    ))

    mode = "REAL" if api_key else "MOCK"
    print(f"\n[CEO Assistant | {mode}]")
    print(resp.answer)
    print(f"\n[{resp.latency_ms:.0f}ms | trace: {resp.trace_id[:8]}]")

    if llm:
        await llm.shutdown()
    await bus.stop()
    await es.close()
    await ds.close()

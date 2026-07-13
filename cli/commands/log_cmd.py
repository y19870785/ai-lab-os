"""CEO Assistant CLI —— 工作记录命令。"""
import asyncio, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

async def run(args):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli log <工作内容>")
        return

    from applications.ceo_assistant.application import CEOAssistant
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
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

    app = CEOAssistant(memory_manager=memory)

    from applications.models import ApplicationRequest
    resp = await app.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input=f"记录: {user_input}",
    ))

    mode = "REAL" if os.getenv("OPENAI_API_KEY") else "MOCK"
    print(f"\n[CEO Assistant | {mode}]")
    print(resp.answer)

    await bus.stop()
    await es.close()

"""CEO Assistant CLI —— 任务命令。"""
import asyncio, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

async def run(args):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    user_input = " ".join(args) if args else ""
    if not user_input:
        user_input = "查看我的待办任务"

    from applications.ceo_assistant.application import CEOAssistant
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from core.memory.session import SessionMemory
    from core.bus.bus import get_bus

    data_dir = os.path.join(os.getcwd(), "data", "sqlite")
    os.makedirs(data_dir, exist_ok=True)

    bus = get_bus(); await bus.start()
    memory = MemoryManager(bus=bus)
    memory.register_store(MemoryType.SESSION, SessionMemory(default_ttl=3600, bus=bus))
    ds = SQLiteDecisionStore(db_path=os.path.join(data_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    app = CEOAssistant(memory_manager=memory)
    from applications.models import ApplicationRequest
    resp = await app.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input=user_input,
    ))

    mode = "REAL" if os.getenv("OPENAI_API_KEY") else "MOCK"
    print(f"\n[CEO Assistant | {mode}]")
    print(resp.answer)

    await bus.stop()
    await ds.close()

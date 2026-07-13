"""CEO Assistant CLI —— 每日简报命令。"""
import asyncio, os, sys, io
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

async def run(args):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

    from core.bus.bus import get_bus
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType, MemoryQuery
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from core.memory.session import SessionMemory
    from datetime import datetime

    data_dir = os.path.join(os.getcwd(), "data", "sqlite")
    os.makedirs(data_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    sm = SessionMemory(default_ttl=3600, bus=bus)
    memory.register_store(MemoryType.SESSION, sm)

    es = SQLiteEpisodicStore(db_path=os.path.join(data_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)

    ds = SQLiteDecisionStore(db_path=os.path.join(data_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    today = datetime.now().strftime("%Y-%m-%d")
    mode = "REAL" if os.getenv("OPENAI_API_KEY") else "MOCK"
    print(f"\n[CEO Assistant | {mode}]")
    print(f"每日简报 -- {today}")
    print("=" * 40)
    print()

    # Retrieve - using retrieve_memory with MemoryQuery
    all_decisions = await memory.retrieve_memory(MemoryQuery(memory_type=MemoryType.DECISION, top_k=50))
    tasks = [r for r in all_decisions if r.content.get("type") == "task" and r.content.get("status") in ("待办", "pending")]

    if tasks:
        print(f"待办任务 ({len(tasks)}):")
        for t in tasks:
            c = t.content
            title = c.get('title', c.get('subject', '无标题'))
            deadline = c.get('deadline', '')
            pri = c.get('priority', '中')
            deadline_str = f" -- 截止: {deadline}" if deadline else ""
            print(f"  [{pri}] {title}{deadline_str}")
    else:
        print("待办任务: 无")

    print()
    all_episodes = await memory.retrieve_memory(MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10))
    episodes = [r for r in all_episodes if r.content.get("type") == "work_log"]

    if episodes:
        print(f"最近工作记录 ({len(episodes)}):")
        for e in episodes[:5]:
            c = e.content
            print(f"  - {c.get('subject', '')[:60]} ({c.get('status', '')})")
    else:
        print("最近工作记录: 无")

    print()
    decisions = [r for r in all_decisions if r.content.get("type") == "decision"]
    if decisions:
        print(f"最近决策 ({len(decisions)}):")
        for d in decisions[:3]:
            c = d.content
            print(f"  - {c.get('chosen', '')[:80]} (结果: {c.get('outcome_status', 'pending')})")
    else:
        print("最近决策: 无")

    print()
    if tasks:
        print("建议优先处理:")
        priority_order = {"高": 1, "中": 2, "低": 3}
        sorted_tasks = sorted(tasks, key=lambda t: priority_order.get(t.content.get("priority", "中"), 2))[:3]
        for i, t in enumerate(sorted_tasks):
            print(f"  {i+1}. {t.content.get('title', '')[:60]} ({t.content.get('priority', '中')}优先级)")

    await bus.stop()
    await es.close()
    await ds.close()

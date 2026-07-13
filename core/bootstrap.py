"""AI-Lab Bootstrap —— 统一启动入口。

按正确顺序初始化所有子系统：
    Config → Database → EventBus → Providers → Memory → Knowledge
    → Tools → Agents → Workflow → Scheduler → Task → Coordination → Applications → API
"""

from __future__ import annotations
import os
import logging
from typing import Any

from core.lifecycle import LifecycleManager

logger = logging.getLogger("ai-lab.bootstrap")


async def bootstrap(
    config_path: str = "",
    env: str = "",
    enable_api: bool = False,
) -> LifecycleManager:
    """初始化 AI-Lab 全栈。

    Returns:
        LifecycleManager: 已初始化的生命周期管理器。
    """
    lm = LifecycleManager()

    # 1. Config
    from core.config import config
    lm.register("config", config,
                lambda c: _noop(), lambda c: _noop())

    # 2. EventBus
    from core.bus.bus import get_bus
    bus = get_bus()
    lm.register("eventbus", bus,
                lambda b: b.start(), lambda b: b.stop())

    # 3. Database
    from core.database.manager import DatabaseManager
    db = DatabaseManager()
    lm.register("database", db,
                lambda d: _noop(), lambda d: d.close_all())

    # Start core infrastructure
    await lm.startup()

    # 4. Providers
    from core.providers.factory import ProviderFactory
    from core.providers.registry import ProviderRegistry
    from core.providers.config import default_configs
    provider_registry = ProviderRegistry()
    provider_factory = ProviderFactory(provider_registry)
    provider_factory.register_builtins()
    providers = await provider_factory.initialize_all(default_configs())
    lm.register("providers", provider_factory,
                lambda f: _noop(), lambda f: f.registry.shutdown_all())

    # 5. Memory
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.storage.sqlite_semantic import SQLiteSemanticStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from core.memory.session import SessionMemory
    import tempfile, os as _os

    data_dir = _os.path.join(_os.getcwd(), "data", "sqlite")
    _os.makedirs(data_dir, exist_ok=True)

    memory_mgr = MemoryManager(bus=bus)
    sm = SessionMemory(default_ttl=3600, bus=bus)
    memory_mgr.register_store(MemoryType.SESSION, sm)
    es = SQLiteEpisodicStore(db_path=_os.path.join(data_dir, "episodic.db"))
    await es.initialize()
    memory_mgr.register_store(MemoryType.EPISODIC, es)
    ss = SQLiteSemanticStore(db_path=_os.path.join(data_dir, "semantic.db"))
    await ss.initialize()
    memory_mgr.register_store(MemoryType.SEMANTIC, ss)
    ds = SQLiteDecisionStore(db_path=_os.path.join(data_dir, "decision.db"))
    await ds.initialize()
    memory_mgr.register_store(MemoryType.DECISION, ds)
    lm.register("memory", memory_mgr,
                lambda m: _noop(),
                lambda m: asyncio_gather(es.close(), ss.close(), ds.close()))

    # 6. Knowledge
    from core.knowledge.manager import KnowledgeManager
    from core.knowledge.protocol import KnowledgeStore as KS
    # Simple in-memory store for bootstrap
    class _InMemoryKnowledgeStore(KS):
        def __init__(self): self._items = {}
        async def save(self, item): self._items[item.id] = item
        async def get(self, id): return self._items.get(id)
        async def query(self, q): return []
        async def delete(self, id): self._items.pop(id, None)
        async def count(self, **kw): return len(self._items)
        async def initialize(self): pass
        async def close(self): pass
        async def batch_save(self, items):
            for item in items: self._items[item.id] = item
    try:
        emb_provider = provider_factory.get_embedding("openai")
    except Exception:
        emb_provider = provider_factory.get_embedding("mock")
    try:
        vec_provider = provider_factory.get_vector("chroma")
    except Exception:
        vec_provider = provider_factory.get_vector("mock")
    inject_store = _InMemoryKnowledgeStore()
    await inject_store.initialize()
    knowledge_mgr = KnowledgeManager(
        store=inject_store,
        embedding_provider=emb_provider,
        vector_provider=vec_provider,
        bus=bus,
    )
    knowledge_mgr.initialize()
    lm.register("knowledge", knowledge_mgr,
                lambda k: _noop(), lambda k: k.close())

    # 7. Tool Runtime
    from core.tools.registry import ToolRegistry
    from core.tools.executor import ToolExecutor
    from core.tools.builtin.echo import EchoTool
    from core.tools.builtin.calculator import CalculatorTool
    tool_registry = ToolRegistry()
    for tool in [EchoTool(), CalculatorTool()]:
        tool_registry.register(tool.info, tool.__class__)
    tool_executor = ToolExecutor(registry=tool_registry)
    lm.register("tools", tool_executor,
                lambda t: _noop(), lambda t: _noop())

    # 8. Agent Runtime
    from core.agents.models import AgentInfo
    from core.agents.runtime import DefaultAgentRuntime
    from core.agents.config import AgentConfig
    try:
        llm = provider_factory.get_llm("openai")
    except Exception:
        llm = provider_factory.get_llm("mock")
    agent_info = AgentInfo(name="default-agent", description="Default AI-Lab Agent")
    agent_config = AgentConfig(memory_enabled=True, knowledge_enabled=True, tools_enabled=True)
    agent_runtime = DefaultAgentRuntime(
        info=agent_info, llm_provider=llm,
        memory_manager=memory_mgr, knowledge_manager=knowledge_mgr,
        tool_registry=tool_registry, config=agent_config, bus=bus,
    )
    await agent_runtime.initialize()
    lm.register("agent", agent_runtime,
                lambda a: _noop(), lambda a: a.shutdown())

    # 9. Workflow
    from core.workflow.runtime import WorkflowRuntime
    workflow_runtime = WorkflowRuntime()
    await workflow_runtime.initialize()
    lm.register("workflow", workflow_runtime,
                lambda w: _noop(), lambda w: w.shutdown())

    # 10. Scheduler
    from core.scheduler.runtime import SchedulerRuntime
    scheduler_runtime = SchedulerRuntime()
    await scheduler_runtime.initialize()
    lm.register("scheduler", scheduler_runtime,
                lambda s: _noop(), lambda s: s.shutdown())

    # 11. Task
    from core.task.manager import TaskManager
    from core.task.runtime import TaskRuntime
    task_mgr = TaskManager()
    task_runtime = TaskRuntime(manager=task_mgr, workflow_runtime=workflow_runtime,
                               scheduler_runtime=scheduler_runtime)
    await task_runtime.initialize()
    lm.register("task", task_runtime,
                lambda t: _noop(), lambda t: t.shutdown())

    # 12. Coordination
    from core.coordination.orchestrator import AgentOrchestrator
    orchestrator = AgentOrchestrator(
        agent_registry=None,
        bus=bus,
    )
    await orchestrator.initialize()
    lm.register("coordination", orchestrator,
                lambda o: _noop(), lambda o: o.shutdown())

    # 13. Application
    from applications.runtime import ApplicationRuntime
    from applications.registry import ApplicationRegistry
    from applications.models import ApplicationInfo, ApplicationManifest
    app_registry = ApplicationRegistry()
    app_runtime = ApplicationRuntime(
        registry=app_registry,
        orchestrator=orchestrator,
        agent_runtime=agent_runtime,
        knowledge_manager=knowledge_mgr,
        memory_manager=memory_mgr,
        bus=bus,
    )
    await app_runtime.initialize()

    # Register alpha_assistant
    app_info = ApplicationInfo(name="alpha_assistant", version="1.0.0")
    app_manifest = ApplicationManifest(
        name="alpha_assistant", version="1.0", entrypoint="alpha",
        required_agents=["default-agent"],
    )
    await app_runtime.register_application(app_info, app_manifest)

    # Register ceo-assistant
    ceo_info = ApplicationInfo(
        name="ceo-assistant", version="0.32.0",
        description="CEO个人工作总控助手",
        entrypoint="applications.ceo_assistant.application:CEOAssistant",
    )
    ceo_manifest = ApplicationManifest(
        name="ceo-assistant", version="0.32.0",
        entrypoint="applications.ceo_assistant.application:CEOAssistant",
        required_agents=["default-agent"],
        required_providers=["openai", "chroma"],
        required_permissions=["memory:read", "memory:write", "knowledge:read", "knowledge:write"],
    )
    await app_runtime.register_application(ceo_info, ceo_manifest)

    lm.register("applications", app_runtime,
                lambda a: _noop(), lambda a: a.shutdown())

    logger.info("AI-Lab bootstrap complete.")
    return lm


async def _noop(*args, **kwargs):
    pass


async def asyncio_gather(*coros):
    import asyncio
    await asyncio.gather(*[c for c in coros if c], return_exceptions=True)

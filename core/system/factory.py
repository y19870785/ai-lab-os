"""AI-Lab 唯一异步 Composition Root。"""

from __future__ import annotations

from applications.ceo_assistant.application import CEOAssistant
from applications.config import ApplicationConfig
from applications.registry import ApplicationRegistry
from applications.runtime import ApplicationRuntime
from core.agents.config import AgentConfig
from core.agents.models import AgentInfo
from core.agents.runtime import DefaultAgentRuntime
from core.bus.bus import MemoryBus
from core.coordination.orchestrator import AgentOrchestrator
from core.database.manager import DatabaseManager
from core.knowledge.manager import KnowledgeManager
from core.knowledge.sqlite_store import SQLiteKnowledgeStore
from core.memory.manager import MemoryManager
from core.memory.models import MemoryType
from core.memory.session import SessionMemory
from core.memory.storage.sqlite_decision import SQLiteDecisionStore
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.memory.storage.sqlite_semantic import SQLiteSemanticStore
from core.providers.embedding.mock import MockEmbeddingProvider
from core.providers.embedding.openai import OpenAIEmbeddingProvider
from core.providers.factory import ProviderFactory
from core.providers.llm.mock import MockLLMProvider
from core.providers.llm.openai import OpenAILLMProvider
from core.providers.models import ProviderType
from core.providers.registry import ProviderRegistry
from core.providers.vector.chroma import ChromaVectorProvider
from core.providers.vector.mock import MockVectorProvider
from core.scheduler.config import SchedulerConfig
from core.scheduler.jobs import JobExecutor
from core.scheduler.persistence import SchedulerPersistence
from core.scheduler.registry import SchedulerRegistry
from core.scheduler.runtime import SchedulerRuntime
from core.system.container import SystemContainer
from core.system.exceptions import ProviderNotConfiguredError
from core.system.settings import SystemSettings
from core.task.manager import TaskManager
from core.task.runtime import TaskRuntime
from core.tools.builtin.calculator import CalculatorTool
from core.tools.builtin.echo import EchoTool
from core.tools.executor import ToolExecutor
from core.tools.registry import ToolRegistry
from core.workflow.executor import WorkflowExecutor
from core.workflow.registry import WorkflowRegistry
from core.workflow.runtime import WorkflowRuntime
from core.user_tasks import SQLiteUserTaskRepository, UserTaskService


def _validate_provider_settings(settings: SystemSettings) -> None:
    if settings.provider_mode == "invalid":
        raise ProviderNotConfiguredError(
            "Provider configuration is incomplete. Set AI_LAB_PROVIDER_MODE=mock "
            "for explicit offline mode, or configure API key, base URL and model."
        )
    if settings.provider_mode == "real":
        missing = [name for name, value in (
            ("api_key", settings.api_key),
            ("base_url", settings.base_url),
            ("model", settings.model),
        ) if not value]
        if missing:
            raise ProviderNotConfiguredError(
                f"Real provider configuration missing: {', '.join(missing)}"
            )


def _configure_providers(settings: SystemSettings):
    registry = ProviderRegistry()
    factory = ProviderFactory(registry)
    factory.register_builtins()

    if settings.provider_mode in {"mock", "test"}:
        registry.register(ProviderType.LLM, "selected", MockLLMProvider)
        llm = registry.get(ProviderType.LLM, "selected")
        if settings.enable_knowledge:
            registry.register(ProviderType.EMBEDDING, "selected", MockEmbeddingProvider)
            registry.register(ProviderType.VECTOR, "selected", MockVectorProvider)
            embedding = registry.get(ProviderType.EMBEDDING, "selected")
            vector = registry.get(ProviderType.VECTOR, "selected")
            return registry, factory, llm, (embedding, vector), embedding, vector
        return registry, factory, llm, (), None, None

    registry.register(
        ProviderType.LLM,
        "selected",
        lambda: OpenAILLMProvider(
            api_key=settings.api_key,
            base_url=settings.base_url,
            model=settings.model,
            timeout=settings.timeout,
            max_retries=settings.max_retries,
        ),
    )
    llm = registry.get(ProviderType.LLM, "selected")

    embedding = None
    vector = None
    extras = []
    if settings.enable_knowledge:
        if not settings.embedding_model or settings.vector_provider != "chroma":
            raise ProviderNotConfiguredError(
                "Knowledge requires AI_LAB_EMBEDDING_MODEL and AI_LAB_VECTOR_PROVIDER=chroma"
            )
        registry.register(
            ProviderType.EMBEDDING,
            "selected",
            lambda: OpenAIEmbeddingProvider(
                api_key=settings.api_key,
                base_url=settings.base_url,
                model=settings.embedding_model,
                timeout=settings.timeout,
            ),
        )
        registry.register(
            ProviderType.VECTOR,
            "selected",
            lambda: ChromaVectorProvider(persist_dir=str(settings.chroma_dir)),
        )
        embedding = registry.get(ProviderType.EMBEDDING, "selected")
        vector = registry.get(ProviderType.VECTOR, "selected")
        extras.extend([embedding, vector])
    return registry, factory, llm, tuple(extras), embedding, vector


async def create_system(settings: SystemSettings) -> SystemContainer:
    """Construct one dependency graph without starting any lifecycle twice."""

    _validate_provider_settings(settings)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.sqlite_dir.mkdir(parents=True, exist_ok=True)

    event_bus = MemoryBus()
    database_manager = DatabaseManager(base_path=settings.sqlite_dir)
    provider_registry, provider_factory, llm, extras, embedding, vector = _configure_providers(settings)

    memory_manager = MemoryManager(bus=event_bus)
    session_store = SessionMemory(default_ttl=3600, bus=event_bus)
    episodic_store = SQLiteEpisodicStore(
        db_path=str(settings.sqlite_dir / "episodic.db"),
        db_manager=database_manager,
    )
    semantic_store = SQLiteSemanticStore(
        db_path=str(settings.sqlite_dir / "semantic.db"),
        db_manager=database_manager,
    )
    decision_store = SQLiteDecisionStore(
        db_path=str(settings.sqlite_dir / "decision.db"),
        db_manager=database_manager,
    )
    memory_stores = (session_store, episodic_store, semantic_store, decision_store)
    for memory_type, store in zip(MemoryType, memory_stores):
        memory_manager.register_store(memory_type, store)

    user_task_repository = None
    user_task_service = None
    if settings.enable_user_tasks:
        user_task_repository = SQLiteUserTaskRepository(
            database_manager, settings.sqlite_dir / "tasks.db"
        )
        user_task_service = UserTaskService(user_task_repository, bus=event_bus)

    knowledge_manager = None
    if settings.enable_knowledge:
        knowledge_manager = KnowledgeManager(
            store=SQLiteKnowledgeStore(settings.sqlite_dir / "knowledge.db"),
            embedding_provider=embedding,
            vector_provider=vector,
            bus=event_bus,
        )

    tool_registry = ToolRegistry()
    for tool_class in (EchoTool, CalculatorTool):
        info = tool_class().info
        tool_registry.register(info, tool_class)
    tool_executor = ToolExecutor(registry=tool_registry, bus=event_bus)

    agent_info = AgentInfo(name="default-agent", description="AI-Lab default agent")
    agent_config = AgentConfig(
        memory_enabled=True,
        knowledge_enabled=settings.enable_knowledge,
        tools_enabled=True,
        provider_name="openai" if settings.provider_mode == "real" else "mock",
        model=settings.model,
    )
    agent_runtime = DefaultAgentRuntime(
        info=agent_info,
        llm_provider=llm,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
        config=agent_config,
        bus=event_bus,
    )

    workflow_registry = WorkflowRegistry()
    workflow_executor = WorkflowExecutor(
        agent_runtime=agent_runtime,
        tool_executor=tool_executor,
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        bus=event_bus,
    )
    workflow_runtime = WorkflowRuntime(
        registry=workflow_registry,
        executor=workflow_executor,
        bus=event_bus,
    )

    scheduler_runtime = None
    if settings.enable_scheduler:
        scheduler_persistence = SchedulerPersistence(str(settings.sqlite_dir / "scheduler.db"))
        scheduler_runtime = SchedulerRuntime(
            registry=SchedulerRegistry(),
            executor=JobExecutor(workflow_runtime=workflow_runtime, bus=event_bus),
            persistence=scheduler_persistence,
            config=SchedulerConfig(db_path=str(settings.sqlite_dir / "scheduler.db")),
            bus=event_bus,
        )

    task_runtime = TaskRuntime(
        manager=TaskManager(),
        workflow_runtime=workflow_runtime,
        scheduler_runtime=scheduler_runtime,
        bus=event_bus,
    )

    coordination_runtime = None
    if settings.enable_coordination:
        coordination_runtime = AgentOrchestrator(bus=event_bus)

    application_registry = ApplicationRegistry()
    ceo_assistant = CEOAssistant(
        memory_manager=memory_manager,
        knowledge_manager=knowledge_manager,
        llm_provider=llm,
        embedding_provider=embedding,
        user_task_service=user_task_service,
        config=ApplicationConfig(
            provider_mode=settings.provider_mode,
            default_model=settings.model,
        ),
        bus=event_bus,
    )
    application_registry.register(
        ceo_assistant.info,
        ceo_assistant.manifest,
        instance=ceo_assistant,
    )
    application_runtime = ApplicationRuntime(
        registry=application_registry,
        orchestrator=coordination_runtime,
        agent_runtime=agent_runtime,
        knowledge_manager=knowledge_manager,
        memory_manager=memory_manager,
        config=ApplicationConfig(provider_mode=settings.provider_mode),
        bus=event_bus,
    )

    return SystemContainer(
        settings=settings,
        event_bus=event_bus,
        database_manager=database_manager,
        provider_registry=provider_registry,
        provider_factory=provider_factory,
        llm_provider=llm,
        providers=(llm, *extras),
        memory_manager=memory_manager,
        memory_stores=memory_stores,
        knowledge_manager=knowledge_manager,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
        agent_runtime=agent_runtime,
        workflow_runtime=workflow_runtime,
        scheduler_runtime=scheduler_runtime,
        task_runtime=task_runtime,
        user_task_repository=user_task_repository,
        user_task_service=user_task_service,
        coordination_runtime=coordination_runtime,
        application_registry=application_registry,
        application_runtime=application_runtime,
        ceo_assistant=ceo_assistant,
    )

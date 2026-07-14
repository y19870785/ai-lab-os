"""SystemContainer：单进程唯一依赖图与生命周期所有者。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from applications.ceo_assistant.application import CEOAssistant
from applications.registry import ApplicationRegistry
from applications.runtime import ApplicationRuntime
from core.agents.runtime import DefaultAgentRuntime
from core.bus.bus import MemoryBus
from core.coordination.orchestrator import AgentOrchestrator
from core.database.manager import DatabaseManager
from core.knowledge.manager import KnowledgeManager
from core.memory.manager import MemoryManager
from core.memory.protocol import MemoryStore
from core.providers.base import BaseProvider
from core.providers.factory import ProviderFactory
from core.providers.llm.protocol import LLMProvider
from core.providers.registry import ProviderRegistry
from core.scheduler.runtime import SchedulerRuntime
from core.system.exceptions import SystemInitializationError
from core.system.settings import SystemSettings
from core.task.runtime import TaskRuntime
from core.tools.executor import ToolExecutor
from core.tools.protocol import ToolProtocol
from core.tools.registry import ToolRegistry
from core.workflow.runtime import WorkflowRuntime

logger = logging.getLogger("ai-lab.system")


@dataclass
class SystemContainer:
    """Own every process-level service and its explicit lifecycle."""

    settings: SystemSettings
    event_bus: MemoryBus
    database_manager: DatabaseManager
    provider_registry: ProviderRegistry
    provider_factory: ProviderFactory
    llm_provider: LLMProvider
    providers: tuple[BaseProvider, ...]
    memory_manager: MemoryManager
    memory_stores: tuple[MemoryStore, ...]
    knowledge_manager: KnowledgeManager | None
    tool_registry: ToolRegistry
    tool_executor: ToolExecutor
    agent_runtime: DefaultAgentRuntime
    workflow_runtime: WorkflowRuntime
    scheduler_runtime: SchedulerRuntime | None
    task_runtime: TaskRuntime
    coordination_runtime: AgentOrchestrator | None
    application_registry: ApplicationRegistry
    application_runtime: ApplicationRuntime
    ceo_assistant: CEOAssistant
    _started: bool = field(default=False, init=False, repr=False)
    _starting: bool = field(default=False, init=False, repr=False)
    _tool_instances: list[ToolProtocol] = field(default_factory=list, init=False, repr=False)

    async def start(self) -> None:
        """Start all configured services once; roll back on partial failure."""

        if self._started:
            return
        if self._starting:
            raise SystemInitializationError("System startup is already in progress")

        self._starting = True
        logger.info("system.initializing")
        try:
            await self.event_bus.start()
            logger.info("event_bus.started")

            for provider in self.providers:
                await provider.initialize()
            logger.info("providers.initialized")

            for store in self.memory_stores:
                await store.initialize()
            logger.info("memory.initialized")

            if self.knowledge_manager is not None:
                await self.knowledge_manager.initialize()
                logger.info("knowledge.initialized")
            else:
                logger.info("knowledge.disabled")

            for name in self.tool_registry.list_names():
                tool = self.tool_registry.get(name)
                await tool.initialize()
                self._tool_instances.append(tool)
            logger.info("tools.initialized")

            await self.agent_runtime.initialize()
            logger.info("agent.initialized")
            await self.workflow_runtime.initialize()
            logger.info("workflow.initialized")

            if self.scheduler_runtime is not None:
                await self.scheduler_runtime.initialize()
                await self.scheduler_runtime.start()
                logger.info("scheduler.started")
            else:
                logger.info("scheduler.disabled")

            await self.task_runtime.initialize()
            if self.coordination_runtime is not None:
                await self.coordination_runtime.initialize()

            await self.application_runtime.initialize()
            logger.info("applications.registered")
            self._started = True
            logger.info("system.ready")
        except Exception as exc:
            logger.exception("system.initialization.failed")
            await self.shutdown()
            raise SystemInitializationError(str(exc)) from exc
        finally:
            self._starting = False

    async def shutdown(self) -> None:
        """Stop resources in reverse order; every component gets a cleanup chance."""

        if not self._started and not self._starting:
            return
        logger.info("system.shutdown.started")

        async def close_component(name: str, callback) -> None:
            try:
                result = callback()
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception("system.shutdown.component_failed", extra={"component": name})

        await close_component("application_runtime", self.application_runtime.shutdown)
        if self.coordination_runtime is not None:
            await close_component("coordination_runtime", self.coordination_runtime.shutdown)
        await close_component("task_runtime", self.task_runtime.shutdown)
        if self.scheduler_runtime is not None:
            await close_component("scheduler_runtime", self.scheduler_runtime.shutdown)
        await close_component("workflow_runtime", self.workflow_runtime.shutdown)
        await close_component("agent_runtime", self.agent_runtime.shutdown)

        for tool in reversed(self._tool_instances):
            await close_component(f"tool:{tool.info.name}", tool.shutdown)
        self._tool_instances.clear()

        if self.knowledge_manager is not None:
            await close_component("knowledge_manager", self.knowledge_manager.close)
        for store in reversed(self.memory_stores):
            await close_component(f"memory:{store.__class__.__name__}", store.close)
        for provider in reversed(self.providers):
            await close_component(f"provider:{provider.metadata().name}", provider.shutdown)
        await close_component("event_bus", self.event_bus.stop)
        await close_component("database_manager", self.database_manager.close_all)

        self._started = False
        logger.info("system.shutdown.completed")

    async def health(self) -> dict[str, object]:
        """Return honest component state without probing external networks."""

        scheduler_status = "disabled"
        if self.scheduler_runtime is not None:
            scheduler_status = "healthy" if await self.scheduler_runtime.health_check() else "failed"
        return {
            "status": "healthy" if self._started else "not_initialized",
            "provider_mode": self.settings.provider_mode,
            "event_bus": "healthy" if self.event_bus.is_running else "stopped",
            "provider": "healthy" if self.llm_provider.is_available() else "failed",
            "memory": "healthy" if self._started else "not_initialized",
            "knowledge": "healthy" if self.knowledge_manager is not None and self._started else "disabled",
            "scheduler": scheduler_status,
            "coordination": "healthy" if self.coordination_runtime is not None and self._started else "disabled",
            "applications": self.application_registry.count,
        }

    @property
    def started(self) -> bool:
        return self._started

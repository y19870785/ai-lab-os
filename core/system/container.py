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
from core.user_tasks import SQLiteUserTaskRepository, UserTaskService
from core.agents.models import AgentStatus
from core.errors import RuntimeStatus
from core.providers.models import ProviderStatus

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
    user_task_repository: SQLiteUserTaskRepository | None
    user_task_service: UserTaskService | None
    coordination_runtime: AgentOrchestrator | None
    application_registry: ApplicationRegistry
    application_runtime: ApplicationRuntime
    ceo_assistant: CEOAssistant
    _started: bool = field(default=False, init=False, repr=False)
    _starting: bool = field(default=False, init=False, repr=False)
    _stopped: bool = field(default=False, init=False, repr=False)
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

            if self.user_task_service is not None:
                await self.user_task_service.initialize()
                logger.info("user_tasks.initialized")
            else:
                logger.info("user_tasks.disabled")

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
            self._stopped = False
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
        if self.user_task_service is not None:
            await close_component("user_task_service", self.user_task_service.close)
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
        self._stopped = True
        logger.info("system.shutdown.completed")

    async def health(self) -> dict[str, object]:
        """Aggregate actual component state without external network probes."""

        if not self._started:
            return {
                "status": (
                    RuntimeStatus.STOPPED.value
                    if self._stopped else RuntimeStatus.NOT_INITIALIZED.value
                ),
                "provider_mode": self.settings.provider_mode,
                "components": {},
            }

        provider_state = self.llm_provider.metadata().status
        provider_status = {
            ProviderStatus.READY: RuntimeStatus.OK,
            ProviderStatus.DEGRADED: RuntimeStatus.DEGRADED,
            ProviderStatus.UNAVAILABLE: RuntimeStatus.FAILED,
            ProviderStatus.SHUTDOWN: RuntimeStatus.STOPPED,
        }.get(provider_state, RuntimeStatus.NOT_INITIALIZED)

        agent_status = {
            AgentStatus.CREATED: RuntimeStatus.NOT_INITIALIZED,
            AgentStatus.INITIALIZED: RuntimeStatus.NOT_INITIALIZED,
            AgentStatus.READY: RuntimeStatus.OK,
            AgentStatus.RUNNING: RuntimeStatus.OK,
            AgentStatus.IDLE: RuntimeStatus.OK,
            AgentStatus.ERROR: RuntimeStatus.FAILED,
            AgentStatus.DEGRADED: RuntimeStatus.DEGRADED,
            AgentStatus.STOPPED: RuntimeStatus.STOPPED,
            AgentStatus.DESTROYED: RuntimeStatus.STOPPED,
        }.get(self.agent_runtime.info.status, RuntimeStatus.NOT_INITIALIZED)

        scheduler_health = (
            await self.scheduler_runtime.health()
            if self.scheduler_runtime is not None
            else {"status": RuntimeStatus.DISABLED.value}
        )
        database_health = self.database_manager.health()
        memory_health = self.memory_manager.health()
        application_health = await self.application_runtime.health_check()
        user_task_health = (
            await self.user_task_service.health()
            if self.user_task_service is not None
            else {"status": RuntimeStatus.DISABLED.value}
        )
        tool_count = len(self.tool_registry.list_names())
        initialized_tool_count = len(self._tool_instances)
        components: dict[str, dict[str, object]] = {
            "event_bus": {
                "status": RuntimeStatus.OK.value if self.event_bus.is_running
                else RuntimeStatus.STOPPED.value,
            },
            "provider": {
                "status": provider_status.value,
                "mode": self.settings.provider_mode,
                "readiness": provider_state.value,
            },
            "database": database_health,
            "memory": memory_health,
            "knowledge": {
                "status": (
                    RuntimeStatus.DISABLED.value
                    if self.knowledge_manager is None
                    else RuntimeStatus.OK.value
                    if self.knowledge_manager.initialized
                    else RuntimeStatus.NOT_INITIALIZED.value
                ),
            },
            "tools": {
                "status": (
                    RuntimeStatus.OK.value
                    if tool_count > 0 and initialized_tool_count == tool_count
                    else RuntimeStatus.NOT_CONFIGURED.value
                    if tool_count == 0
                    else RuntimeStatus.NOT_INITIALIZED.value
                ),
                "registered": tool_count,
                "initialized": initialized_tool_count,
            },
            "agent": {"status": agent_status.value,
                      "lifecycle": self.agent_runtime.info.status.value},
            "workflow": {
                "status": RuntimeStatus.OK.value
                if self.workflow_runtime.initialized else RuntimeStatus.NOT_INITIALIZED.value,
            },
            "scheduler": scheduler_health,
            "task": {
                "status": RuntimeStatus.OK.value
                if self.task_runtime.initialized else RuntimeStatus.NOT_INITIALIZED.value,
            },
            "user_tasks": user_task_health,
            "coordination": {
                "status": (
                    RuntimeStatus.DISABLED.value
                    if self.coordination_runtime is None
                    else RuntimeStatus.OK.value
                    if self.coordination_runtime.initialized
                    else RuntimeStatus.NOT_INITIALIZED.value
                ),
            },
            "applications": {
                "status": (
                    RuntimeStatus.NOT_CONFIGURED.value
                    if self.application_registry.count == 0
                    else application_health["status"]
                ),
                "registered": self.application_registry.count,
            },
        }

        critical = {
            "event_bus", "provider", "database", "memory", "tools", "applications",
            "agent", "workflow", "task",
        }
        if self.settings.enable_scheduler:
            critical.add("scheduler")
        if self.settings.enable_knowledge:
            critical.add("knowledge")
        if self.settings.enable_user_tasks:
            critical.add("user_tasks")
        top_status = RuntimeStatus.OK
        unavailable_statuses = {
            RuntimeStatus.FAILED.value,
            RuntimeStatus.STOPPED.value,
            RuntimeStatus.NOT_INITIALIZED.value,
            RuntimeStatus.NOT_CONFIGURED.value,
            RuntimeStatus.DISABLED.value,
        }
        for name, component in components.items():
            status = component["status"]
            if status in unavailable_statuses:
                if status == RuntimeStatus.DISABLED.value and name not in critical:
                    continue
                top_status = RuntimeStatus.FAILED if name in critical else RuntimeStatus.DEGRADED
                if top_status == RuntimeStatus.FAILED:
                    break
            elif status == RuntimeStatus.DEGRADED.value and top_status == RuntimeStatus.OK:
                top_status = RuntimeStatus.DEGRADED

        return {
            "status": top_status.value,
            "provider_mode": self.settings.provider_mode,
            "components": components,
        }

    @property
    def started(self) -> bool:
        return self._started

"""Application Runtime —— 业务应用统一入口。

执行链路：
    ApplicationRequest → ApplicationContext → Orchestrator/Agent → Response

不承担业务推理，不直接调用 Provider、数据库、Tool 或 MCP。
"""

from __future__ import annotations
import time
from typing import Any

from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationContext,
    ApplicationRequest, ApplicationResponse, ApplicationStatus,
)
from applications.registry import ApplicationRegistry
from applications.config import ApplicationConfig
from applications.exceptions import ApplicationNotRegisteredError
from core.workspace.models import WorkspaceKey


class ApplicationRuntime:
    """业务应用统一运行时。"""

    def __init__(
        self,
        registry: ApplicationRegistry | None = None,
        orchestrator=None,
        agent_runtime=None,
        knowledge_manager=None,
        memory_manager=None,
        config: ApplicationConfig | None = None,
        bus=None,
    ):
        self._registry = registry or ApplicationRegistry()
        self._orchestrator = orchestrator
        self._agent_runtime = agent_runtime
        self._knowledge = knowledge_manager
        self._memory = memory_manager
        self._config = config or ApplicationConfig()
        self._bus = bus
        self._initialized = False
        self._contexts: dict[str, ApplicationContext] = {}

    # ---- 生命周期 ----

    async def initialize(self) -> None:
        self._initialized = True

    async def shutdown(self) -> None:
        self._contexts.clear()
        self._initialized = False

    async def health_check(self) -> dict[str, Any]:
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "applications": self._registry.count,
            "provider_mode": self._detect_provider_mode(),
        }

    # ---- 应用管理 ----

    async def register_application(
        self,
        info: ApplicationInfo,
        manifest: ApplicationManifest,
        instance=None,
    ) -> None:
        info.status = ApplicationStatus.INITIALIZED
        self._registry.register(info, manifest, instance)
        info.status = ApplicationStatus.READY

    async def list_applications(self) -> list[ApplicationInfo]:
        return self._registry.list()

    # ---- 执行 ----

    async def execute(self, request: ApplicationRequest) -> ApplicationResponse:
        """Dispatch only to a registered application instance."""
        if not self._initialized:
            raise RuntimeError("ApplicationRuntime is not initialized")

        t0 = time.time()
        app_info = self._registry.get_info_by_name(request.application_name)
        app = self._registry.get_instance_by_name(request.application_name)
        if app_info is None or app is None:
            raise ApplicationNotRegisteredError(request.application_name)

        ctx = ApplicationContext(
            application_id=app_info.application_id,
            workspace_key=request.workspace_key,
            environment=request.metadata.get("environment", "development"),
            metadata={"provider_mode": self._detect_provider_mode()},
        )
        self._contexts[ctx.trace_id] = ctx
        metadata = dict(request.metadata)
        metadata.update({
            "provider_mode": self._detect_provider_mode(),
            "environment": ctx.environment,
        })
        app_request = request.model_copy(update={"metadata": metadata})
        response = await app.run(app_request)
        response.latency_ms = response.latency_ms or (time.time() - t0) * 1000
        response.trace_id = response.trace_id or ctx.trace_id
        return response

    # ---- Helpers ----

    def _detect_provider_mode(self) -> str:
        """Return the mode injected by the Composition Root."""
        return self._config.provider_mode

    def get_context(self, trace_id: str) -> ApplicationContext | None:
        return self._contexts.get(trace_id)

    @property
    def app_count(self) -> int:
        return self._registry.count

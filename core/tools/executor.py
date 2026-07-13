"""ToolExecutor — single execution entry point for all tools.

Orchestration chain:
    validator → permission check → sandbox → execute → metrics → audit → return result
Agent Runtime must go through this; never call tools directly.
"""
from __future__ import annotations
import time
from typing import TYPE_CHECKING

from core.tools.models import ToolRequest, ToolResult, ToolInfo
from core.tools.protocol import ToolProtocol
from core.tools.validator import ToolValidator
from core.tools.permissions import PermissionManager
from core.tools.sandbox import ToolSandbox
from core.tools.metrics import ToolMetricsCollector
from core.tools.audit import ToolAuditLogger
from core.tools.events import publish_tool_event, ToolEventTypes
from core.tools.exceptions import ToolError, ToolNotFoundError, ToolNotReadyError, ToolValidationError, ToolPermissionDeniedError
from core.tools.config import ToolConfig

if TYPE_CHECKING:
    from core.tools.registry import ToolRegistry


class ToolExecutor:
    """The ONLY execution entry point for all tools.

    Agent Runtime calls ToolExecutor.execute() — never calls tools directly.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: PermissionManager | None = None,
        sandbox: ToolSandbox | None = None,
        metrics: ToolMetricsCollector | None = None,
        audit: ToolAuditLogger | None = None,
        config: ToolConfig | None = None,
        bus=None,
    ):
        self._registry = registry
        self._permissions = permission_manager or PermissionManager()
        self._sandbox = sandbox or ToolSandbox()
        self._metrics = metrics or ToolMetricsCollector()
        self._audit = audit or ToolAuditLogger()
        self._config = config or ToolConfig()
        self._bus = bus
        self._validator = ToolValidator()

    async def execute(self, request: ToolRequest) -> ToolResult:
        """Execute a tool through the full orchestration chain.

        Chain: lookup → validate → permission → sandbox → execute → metrics → audit → result
        """
        start = time.perf_counter()

        try:
            info = self._registry.get_info(request.tool_name)
            # 1. Validate arguments
            if self._config.permission_check_enabled:
                self._validator.validate(request, info)

            # 2. Permission check
            if self._config.permission_check_enabled:
                self._permissions.check(info)

            # 3. Get or create tool instance
            tool = self._registry.get(request.tool_name)

            # 4. Sandboxed execution
            result = await self._sandbox.execute(tool.execute, request, info)

            # 5. Attach latency
            latency_ms = (time.perf_counter() - start) * 1000
            result.latency_ms = latency_ms

            # 6. Metrics
            if self._config.metrics_enabled:
                self._metrics.record(
                    info.name,
                    success=result.success,
                    latency_ms=latency_ms,
                    timeout=(result.error is not None and "timed out" in str(result.error).lower()),
                )

            # 7. Audit
            if self._config.audit_enabled:
                self._audit.record(info, request, result)

            # 8. Publish event
            event_type = ToolEventTypes.EXECUTED if result.success else ToolEventTypes.FAILED
            if result.error and "timed out" in str(result.error).lower():
                event_type = ToolEventTypes.TIMEOUT
            await publish_tool_event(
                self._bus,
                event_type=event_type,
                tool_name=info.name,
                agent_id=request.agent_id,
                session_id=request.session_id,
                extra={"success": result.success, "latency_ms": latency_ms},
            )

            return result

        except (ToolNotFoundError, ToolNotReadyError, ToolValidationError, ToolPermissionDeniedError) as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return ToolResult(success=False, error=str(e), latency_ms=latency_ms)

    async def execute_by_name(
        self,
        tool_name: str,
        arguments: dict | None = None,
        agent_id: str = "",
        session_id: str = "",
        trace_id: str = "",
    ) -> ToolResult:
        """Convenience: execute a tool by name with inline arguments."""
        request = ToolRequest(
            tool_name=tool_name,
            arguments=arguments or {},
            agent_id=agent_id,
            session_id=session_id,
            trace_id=trace_id,
        )
        return await self.execute(request)

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def metrics(self) -> ToolMetricsCollector:
        return self._metrics

    @property
    def audit(self) -> ToolAuditLogger:
        return self._audit

    @property
    def config(self) -> ToolConfig:
        return self._config

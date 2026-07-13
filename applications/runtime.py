"""Application Runtime —— 业务应用统一入口。

执行链路：
    ApplicationRequest → ApplicationContext → Orchestrator/Agent → Response

不承担业务推理，不直接调用 Provider、数据库、Tool 或 MCP。
"""

from __future__ import annotations
import time
import os
from typing import Any

from applications.models import (
    ApplicationInfo, ApplicationManifest, ApplicationContext,
    ApplicationRequest, ApplicationResponse, ApplicationStatus,
)
from applications.registry import ApplicationRegistry
from applications.config import ApplicationConfig
from core.provider_mode import detect_provider_mode as _detect_mode
from applications.exceptions import ApplicationInitError, ApplicationExecutionError
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
        """执行业务应用请求。

        这是 Application Layer 的唯一入口。
        """
        if not self._initialized:
            await self.initialize()

        # 确保 .env 已加载（API 模式下不会自动加载；已设环境变量时不覆盖，保持测试隔离）
        if not os.getenv("AI_LAB_DOTENV_LOADED") and not os.getenv("OPENAI_API_KEY"):
            try:
                from dotenv import load_dotenv
                load_dotenv()
                os.environ["AI_LAB_DOTENV_LOADED"] = "1"
            except Exception:
                pass

        t0 = time.time()
        app_info = self._resolve_application(request.application_name)

        # 构建上下文
        ctx = ApplicationContext(
            application_id=app_info.application_id,
            workspace_key=request.workspace_key,
            environment=os.getenv("AI_LAB_ENV", "dev"),
            metadata={"provider_mode": self._detect_provider_mode()},
        )
        self._contexts[ctx.trace_id] = ctx

        try:
            # 如果有 Orchestrator，走多 Agent 协调
            if self._orchestrator:
                from core.coordination.models import TeamConfig, AgentRole, AgentRoleType
                # 创建临时 Team
                team = TeamConfig(
                    name=f"app-{app_info.name}",
                    agents=["default-agent"],
                    roles={"default-agent": AgentRole(role_type=AgentRoleType.EXECUTOR, name="executor")},
                )
                await self._orchestrator.create_team(team)
                coord_result = await self._orchestrator.coordinate(
                    goal=request.user_input,
                    context={"session_id": ctx.session_id, "team_id": team.team_id},
                )
                answer = coord_result.merged_result
            elif self._agent_runtime:
                # 单 Agent 模式
                from core.agents.models import AgentRequest
                agent_req = AgentRequest(
                    user_input=request.user_input,
                    session_id=ctx.session_id,
                    agent_id="default-agent",
                    memory_enabled=True,
                    knowledge_enabled=True,
                    tools_enabled=True,
                    trace_id=ctx.trace_id,
                )
                resp = await self._agent_runtime.run(agent_req)
                answer = resp.answer
            else:
                # 无 Agent Runtime 时，尝试直接用 LLM Provider
                llm = None
                try:
                    from core.providers.llm.openai import OpenAILLMProvider
                    from core.providers.llm.protocol import LLMRequest, Message
                    llm = OpenAILLMProvider()
                    await llm.initialize()
                    resp = await llm.generate(LLMRequest(
                        messages=[Message(role="user", content=request.user_input)],
                        model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
                        max_tokens=4096,
                    ))
                    answer = resp.content or "[empty response]"
                except Exception:
                    answer = f"[mock] Echo: {request.user_input}"
                finally:
                    if llm:
                        try:
                            await llm.shutdown()
                        except Exception:
                            pass

            mode = self._detect_provider_mode()
            if mode == "mock":
                answer = f"[MOCK MODE] {answer}\n\n(Set OPENAI_API_KEY to use real LLM)"

            return ApplicationResponse(
                application_id=app_info.application_id,
                answer=answer,
                status="ok",
                latency_ms=(time.time() - t0) * 1000,
                trace_id=ctx.trace_id,
                mode=mode,
            )

        except Exception as e:
            return ApplicationResponse(
                application_id=app_info.application_id,
                answer="",
                status="error",
                error=str(e),
                latency_ms=(time.time() - t0) * 1000,
                trace_id=ctx.trace_id,
                mode=self._detect_provider_mode(),
            )

    # ---- Helpers ----

    def _resolve_application(self, name: str) -> ApplicationInfo:
        apps = self._registry.find_by_name(name)
        if apps:
            return apps[0]
        # 如果没有注册应用，创建默认
        info = ApplicationInfo(name=name or "default", description="Auto-created application")
        manifest = ApplicationManifest(name=info.name, entrypoint="default")
        self._registry.register(info, manifest)
        return info

    def _detect_provider_mode(self) -> str:
        """检测当前 Provider 模式。"""
        if self._config.provider_mode != "auto":
            return self._config.provider_mode
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_LAB_LLM_API_KEY", "")
        return "real" if api_key and len(api_key) > 10 else "mock"

    def get_context(self, trace_id: str) -> ApplicationContext | None:
        return self._contexts.get(trace_id)

    @property
    def app_count(self) -> int:
        return self._registry.count

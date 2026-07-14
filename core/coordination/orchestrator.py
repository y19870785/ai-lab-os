"""Agent Orchestrator —— Multi-Agent 协作唯一入口。

负责：
- 创建 Agent Team
- 分配任务（通过 Planner）
- 调度 Agent 执行
- 管理协作上下文
- 收集并合并结果

不直接执行任何业务逻辑。只做协调。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from core.coordination.models import (
    TeamConfig, CollaborationContext, CoordinationResult,
    CoordinationStatus, AgentTask, DelegationStatus,
)
from core.coordination.protocol import OrchestratorProtocol
from core.coordination.registry import AgentTeamRegistry
from core.coordination.planner import MultiAgentPlanner
from core.coordination.delegation import TaskDelegator
from core.coordination.communication import AgentMessageBus
from core.coordination.merger import RuleBasedMerger
from core.coordination.events import publish_coordination_event, CoordinationEventTypes
from core.coordination.config import CoordinationConfig
from core.coordination.exceptions import (
    OrchestrationError, TeamNotFoundError,
)


class AgentOrchestrator(OrchestratorProtocol):
    """Agent Orchestrator —— 多 Agent 协调器。

    整个 Multi-Agent 系统的唯一入口点。
    Application 层只和 Orchestrator 交互。
    """

    def __init__(
        self,
        registry: AgentTeamRegistry | None = None,
        planner: MultiAgentPlanner | None = None,
        delegator: TaskDelegator | None = None,
        message_bus: AgentMessageBus | None = None,
        merger=None,
        agent_registry=None,  # 核心 AgentRegistry（来自 core.agents）
        config: CoordinationConfig | None = None,
        bus=None,  # 底层 Event Bus
    ):
        self._registry = registry or AgentTeamRegistry()
        self._planner = planner or MultiAgentPlanner(self._registry)
        self._delegator = delegator or TaskDelegator(bus=bus)
        self._message_bus = message_bus or AgentMessageBus(bus=bus)
        self._merger = merger or RuleBasedMerger()
        self._agent_registry = agent_registry
        self._config = config or CoordinationConfig()
        self._bus = bus

        # 运行时状态
        self._contexts: dict[str, CollaborationContext] = {}  # session_id -> context
        self._teams: dict[str, TeamConfig] = {}
        self._initialized = False

    # ---- Lifecycle ----

    async def initialize(self) -> None:
        await self._message_bus.initialize()
        self._initialized = True

    async def shutdown(self) -> None:
        await self._message_bus.shutdown()
        self._contexts.clear()
        self._teams.clear()
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    # ---- Team Management ----

    async def create_team(self, config: TeamConfig) -> None:
        self._registry.register_team(config)
        self._teams[config.team_id] = config

        # 注册 roles
        for agent_id, role in config.roles.items():
            self._registry.register_role(role)
            self._registry.assign_role(agent_id, role.name)

        await publish_coordination_event(
            self._bus,
            CoordinationEventTypes.TEAM_CREATED,
            payload={"team_id": config.team_id, "agent_count": len(config.agents)},
        )

    # ---- Core Coordination ----

    async def coordinate(
        self,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> CoordinationResult:
        """执行多 Agent 协作。

        这是整个 Multi-Agent 系统的主要入口。
        """
        if not self._initialized:
            await self.initialize()

        session_id = context.get("session_id", f"coord-{int(time.time())}") if context else f"coord-{int(time.time())}"

        # 创建协作上下文
        collab_ctx = CollaborationContext(
            session_id=session_id,
            goal=goal,
            variables=context or {},
        )
        self._contexts[session_id] = collab_ctx

        t0 = time.time()
        errors = []

        try:
            # 1. 获取 Team
            team_id = (context or {}).get("team_id", "")
            if team_id:
                team = self._teams.get(team_id)
                if not team:
                    team = self._registry.get_team(team_id)
            else:
                # 使用第一个注册的 team
                teams = self._registry.list_teams()
                if not teams:
                    raise OrchestrationError(session_id, "No team registered")
                team = teams[0]

            collab_ctx.status = CoordinationStatus.PLANNING

            await publish_coordination_event(
                self._bus,
                CoordinationEventTypes.ORCHESTRATION_STARTED,
                payload={"session_id": session_id, "goal": goal, "team_id": team.team_id},
            )

            # 2. 规划
            tasks = await self._planner.plan(goal, team, context)
            collab_ctx.plan = [t.model_dump() for t in tasks]
            collab_ctx.active_agents = team.agents

            # 3. 调度执行
            collab_ctx.status = CoordinationStatus.DISPATCHING

            agent_results = {}
            for task in tasks:
                collab_ctx.status = CoordinationStatus.RUNNING

                # 委派任务
                await self._delegator.delegate(task)

                # 等待完成
                status = DelegationStatus.PENDING
                waited = 0
                while status in (DelegationStatus.PENDING, DelegationStatus.ACCEPTED, DelegationStatus.RUNNING):
                    await asyncio.sleep(0.1)
                    waited += 0.1
                    status = await self._delegator.get_status(task.task_id)
                    if waited > task.timeout:
                        task.status = DelegationStatus.TIMEOUT
                        task.error = "Timeout"
                        errors.append(f"{task.title}: timeout")
                        break

                # 收集结果
                result = await self._delegator.get_result(task.task_id)
                agent_results[task.assigned_agent] = result
                collab_ctx.intermediate_results[task.assigned_agent] = result

            # 4. 合并结果
            collab_ctx.status = CoordinationStatus.MERGING
            merged = await self._merger.merge(agent_results, collab_ctx)

            # 5. 完成
            collab_ctx.status = CoordinationStatus.COMPLETED

            await publish_coordination_event(
                self._bus,
                CoordinationEventTypes.ORCHESTRATION_COMPLETED,
                payload={
                    "session_id": session_id,
                    "agent_count": len(team.agents),
                    "task_count": len(tasks),
                },
            )

            total_ms = (time.time() - t0) * 1000
            return CoordinationResult(
                session_id=session_id,
                status=CoordinationStatus.COMPLETED,
                goal=goal,
                agent_results=agent_results,
                merged_result=merged,
                intermediate_steps=collab_ctx.plan,
                total_latency_ms=total_ms,
                agent_count=len(team.agents),
                message_count=self._message_bus.message_count(),
                errors=errors,
            )

        except Exception as e:
            collab_ctx.status = CoordinationStatus.FAILED
            errors.append(str(e))
            await publish_coordination_event(
                self._bus,
                CoordinationEventTypes.ORCHESTRATION_FAILED,
                payload={"session_id": session_id, "error": str(e)},
            )
            return CoordinationResult(
                session_id=session_id,
                status=CoordinationStatus.FAILED,
                goal=goal,
                errors=errors,
                total_latency_ms=(time.time() - t0) * 1000,
            )

    async def get_context(self, session_id: str) -> CollaborationContext | None:
        return self._contexts.get(session_id)

    async def cancel(self, session_id: str) -> bool:
        ctx = self._contexts.get(session_id)
        if ctx is None:
            return False
        ctx.status = CoordinationStatus.CANCELLED
        return True

    def status(self, session_id: str) -> CoordinationStatus:
        ctx = self._contexts.get(session_id)
        return ctx.status if ctx else CoordinationStatus.CREATED

    @property
    def context_count(self) -> int:
        return len(self._contexts)

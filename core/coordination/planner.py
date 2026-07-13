"""Multi-Agent Planner —— 任务分解与 Agent 分配。

初期：RuleBasedPlanner（简单分解）
预留：LLMPlanner（LLM 驱动的计划生成）
"""

from __future__ import annotations

from typing import Any

from core.coordination.models import (
    AgentRoleType, AgentTask, CollaborationContext, TeamConfig,
)
from core.coordination.registry import AgentTeamRegistry


class MultiAgentPlanner:
    """多 Agent 任务规划器。

    将目标分解为子任务，分配给合适的 Agent。
    """

    def __init__(self, registry: AgentTeamRegistry | None = None):
        self._registry = registry

    async def plan(
        self,
        goal: str,
        team: TeamConfig,
        context: dict[str, Any] | None = None,
    ) -> list[AgentTask]:
        """根据目标生成子任务列表。

        初期策略：按 Team 中 Agent 的角色分配简单子任务。
        """
        if not team.agents:
            return []

        tasks = []
        ctx = context or {}

        # 对每个 Agent 创建一个子任务
        for i, agent_id in enumerate(team.agents):
            role = team.roles.get(agent_id)
            role_name = role.name if role else "executor"
            role_type = role.role_type if role else AgentRoleType.EXECUTOR

            # 根据角色类型确定任务描述
            task_desc = self._build_task_description(role_type, goal, ctx, i, len(team.agents))

            task = AgentTask(
                parent_task_id="",
                assigned_agent=agent_id,
                assigned_role=role_type,
                title=f"{role_name}: {goal[:50]}",
                description=task_desc,
                input_data={
                    "goal": goal,
                    "role": role_name,
                    "context": ctx,
                    "step_index": i,
                    "total_steps": len(team.agents),
                },
                timeout=300,
                max_retries=2,
                priority=5,
                metadata={"team_id": team.team_id, "step": i},
            )
            tasks.append(task)

        return tasks

    def _build_task_description(
        self,
        role_type: AgentRoleType,
        goal: str,
        context: dict[str, Any],
        step_index: int,
        total_steps: int,
    ) -> str:
        """根据角色类型生成任务描述。"""
        templates = {
            AgentRoleType.PLANNER: f"Plan the approach for: {goal}. Then coordinate with the team.",
            AgentRoleType.RESEARCHER: f"Research information about: {goal}. Gather relevant data and context.",
            AgentRoleType.DEVELOPER: f"Implement the solution for: {goal}. Build the required components.",
            AgentRoleType.REVIEWER: f"Review outputs from the team for: {goal}. Check quality and consistency.",
            AgentRoleType.EXECUTOR: f"Execute the assigned task for: {goal}. Deliver the expected output.",
            AgentRoleType.ANALYST: f"Analyze data related to: {goal}. Provide insights and recommendations.",
            AgentRoleType.COORDINATOR: f"Coordinate the team effort for: {goal}. Ensure all parts come together.",
        }
        base = templates.get(role_type, f"Work on: {goal}")
        return f"[Step {step_index + 1}/{total_steps}] {base}"

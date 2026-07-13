"""Multi-Agent Coordination —— Models Tests."""
import pytest
from core.coordination.models import (
    AgentRole, AgentRoleType, AgentMessage, AgentTask,
    CollaborationContext, TeamConfig, CoordinationResult,
    AgentCapability, DelegationStatus, CoordinationStatus, MessagePriority,
)


class TestModels:

    def test_agent_role_creation(self):
        role = AgentRole(
            role_type=AgentRoleType.RESEARCHER,
            name="researcher",
            description="Research agent",
            capabilities=[AgentCapability(name="research", description="Can research")],
            allowed_tools=["search", "browser"],
            system_prompt_template="You are a researcher.",
        )
        assert role.role_type == AgentRoleType.RESEARCHER
        assert len(role.capabilities) == 1
        assert role.capabilities[0].name == "research"

    def test_agent_message_creation(self):
        msg = AgentMessage(
            sender="agent-1",
            receiver="agent-2",
            conversation_id="conv-1",
            message_type="task",
            payload={"task": "analyze data"},
            priority=MessagePriority.HIGH,
        )
        assert msg.message_id != ""
        assert msg.sender == "agent-1"
        assert msg.priority == MessagePriority.HIGH

    def test_agent_task_creation(self):
        task = AgentTask(
            assigned_agent="agent-1",
            assigned_role=AgentRoleType.EXECUTOR,
            title="Test task",
            description="Run tests",
            timeout=60,
        )
        assert task.task_id != ""
        assert task.status == DelegationStatus.PENDING

    def test_collaboration_context(self):
        ctx = CollaborationContext(
            session_id="s1",
            goal="Build feature X",
            active_agents=["agent-1", "agent-2"],
        )
        assert ctx.status == CoordinationStatus.CREATED
        assert len(ctx.active_agents) == 2

    def test_team_config(self):
        config = TeamConfig(
            name="dev-team",
            description="Development team",
            agents=["agent-1", "agent-2"],
            roles={
                "agent-1": AgentRole(role_type=AgentRoleType.DEVELOPER, name="dev"),
                "agent-2": AgentRole(role_type=AgentRoleType.REVIEWER, name="reviewer"),
            },
        )
        assert config.team_id != ""
        assert len(config.agents) == 2

    def test_coordination_result(self):
        result = CoordinationResult(
            session_id="s1",
            goal="Test goal",
            agent_results={"agent-1": {"answer": "done"}},
            merged_result="All done",
            agent_count=1,
        )
        assert result.status == CoordinationStatus.COMPLETED

    def test_message_priority_values(self):
        assert MessagePriority.LOW.value == "low"
        assert MessagePriority.URGENT.value == "urgent"

    def test_delegation_status_values(self):
        assert DelegationStatus.PENDING.value == "pending"
        assert DelegationStatus.COMPLETED.value == "completed"

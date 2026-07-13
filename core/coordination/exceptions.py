"""Coordination 异常定义。"""


class CoordinationError(Exception):
    """Coordination 基础异常。"""
    pass


class TeamNotFoundError(CoordinationError):
    def __init__(self, team_id: str):
        super().__init__(f"Team '{team_id}' not found")


class RoleNotFoundError(CoordinationError):
    def __init__(self, role_name: str):
        super().__init__(f"Role '{role_name}' not found")


class AgentNotInTeamError(CoordinationError):
    def __init__(self, agent_id: str, team_id: str):
        super().__init__(f"Agent '{agent_id}' not in team '{team_id}'")


class DelegationError(CoordinationError):
    def __init__(self, task_id: str, reason: str):
        super().__init__(f"Delegation failed for '{task_id}': {reason}")


class OrchestrationError(CoordinationError):
    def __init__(self, session_id: str, reason: str):
        super().__init__(f"Orchestration failed for '{session_id}': {reason}")


class MessageDeliveryError(CoordinationError):
    def __init__(self, message_id: str, reason: str):
        super().__init__(f"Message delivery failed for '{message_id}': {reason}")


class MergeError(CoordinationError):
    def __init__(self, reason: str):
        super().__init__(f"Result merge failed: {reason}")


class CoordinationTimeoutError(CoordinationError):
    def __init__(self, operation: str, timeout: float):
        super().__init__(f"'{operation}' timed out after {timeout}s")

"""PermissionManager — permission check before tool execution."""
from __future__ import annotations
from core.tools.models import ToolInfo, ToolPermission
from core.tools.exceptions import ToolPermissionDeniedError

class PermissionManager:
    def __init__(self, agent_permissions: list[str] | None = None):
        self._agent_permissions = set(agent_permissions or [])
    def set_agent_permissions(self, permissions: list[str]) -> None:
        self._agent_permissions = set(permissions)
    def check(self, info: ToolInfo) -> None:
        if not info.permissions:
            return
        for perm in info.permissions:
            if perm.value not in self._agent_permissions:
                raise ToolPermissionDeniedError(f"Agent lacks permission: {perm.value} for tool {info.name}")
    def has_permission(self, info: ToolInfo) -> bool:
        if not info.permissions: return True
        return all(p.value in self._agent_permissions for p in info.permissions)
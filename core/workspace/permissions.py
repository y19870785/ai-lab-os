"""Workspace permissions —— 简单权限检查。"""
from core.workspace.models import UserContext, Permission
from core.workspace.exceptions import WorkspacePermissionError

def check_permission(user: UserContext, required: Permission) -> None:
    if not user.has_permission(required):
        raise WorkspacePermissionError(required.value)

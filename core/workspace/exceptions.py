"""Workspace 异常定义。"""

class WorkspaceError(Exception): pass
class TenantNotFoundError(WorkspaceError):
    def __init__(self, tid): super().__init__(f"Tenant '{tid}' not found")

class WorkspaceNotFoundError(WorkspaceError):
    def __init__(self, wid): super().__init__(f"Workspace '{wid}' not found")

class NamespaceNotFoundError(WorkspaceError):
    def __init__(self, wid, name): super().__init__(f"Namespace '{name}' not found in workspace '{wid}'")

class CrossWorkspaceError(WorkspaceError):
    def __init__(self, w1, w2): super().__init__(f"Cross-workspace access denied: '{w1}' -> '{w2}'")

class WorkspacePermissionError(WorkspaceError):
    def __init__(self, perm): super().__init__(f"Permission denied: {perm}")

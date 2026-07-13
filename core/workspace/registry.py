"""Workspace Registry —— 管理 Tenant / Workspace / Namespace。"""

from __future__ import annotations
from core.workspace.models import Tenant, Workspace, Namespace, WorkspaceKey, WorkspaceStatus
from core.workspace.exceptions import WorkspaceNotFoundError, TenantNotFoundError, CrossWorkspaceError


class WorkspaceRegistry:
    """Workspace + Tenant 注册中心。"""

    def __init__(self):
        self._tenants: dict[str, Tenant] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._namespaces: dict[str, Namespace] = {}

    # ---- Tenant ----

    def register_tenant(self, tenant: Tenant) -> None:
        self._tenants[tenant.tenant_id] = tenant

    def get_tenant(self, tenant_id: str) -> Tenant:
        if tenant_id not in self._tenants:
            raise TenantNotFoundError(tenant_id)
        return self._tenants[tenant_id]

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

    # ---- Workspace ----

    def register_workspace(self, ws: Workspace) -> None:
        self._workspaces[ws.workspace_id] = ws

    def get_workspace(self, workspace_id: str) -> Workspace:
        if workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(workspace_id)
        return self._workspaces[workspace_id]

    def list_workspaces(self, tenant_id: str = "") -> list[Workspace]:
        if tenant_id:
            return [w for w in self._workspaces.values() if w.tenant_id == tenant_id]
        return list(self._workspaces.values())

    def archive_workspace(self, workspace_id: str) -> None:
        ws = self.get_workspace(workspace_id)
        ws.status = WorkspaceStatus.ARCHIVED

    # ---- Namespace ----

    def register_namespace(self, ns: Namespace) -> None:
        key = f"{ns.workspace_id}:{ns.name}"
        self._namespaces[key] = ns

    def get_namespace(self, workspace_id: str, name: str) -> Namespace:
        key = f"{workspace_id}:{name}"
        if key not in self._namespaces:
            from core.workspace.exceptions import NamespaceNotFoundError
            raise NamespaceNotFoundError(workspace_id, name)
        return self._namespaces[key]

    # ---- 校验 ----

    def validate_key(self, key: WorkspaceKey) -> None:
        """校验 WorkspaceKey 的有效性，防止跨 Workspace 访问。"""
        if key.tenant_id and key.tenant_id not in self._tenants:
            raise TenantNotFoundError(key.tenant_id)
        if key.workspace_id and key.workspace_id not in self._workspaces:
            raise WorkspaceNotFoundError(key.workspace_id)

    def ensure_same_workspace(self, key1: WorkspaceKey, key2: WorkspaceKey) -> None:
        """确保两个 key 属于同一 Workspace。"""
        if key1.workspace_id != key2.workspace_id:
            raise CrossWorkspaceError(key1.workspace_id, key2.workspace_id)

    @property
    def tenant_count(self) -> int:
        return len(self._tenants)

    @property
    def workspace_count(self) -> int:
        return len(self._workspaces)

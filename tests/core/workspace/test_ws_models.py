"""Workspace Models Tests。"""
import pytest
from core.workspace.models import (
    Tenant, Workspace, UserContext, WorkspaceKey, Namespace,
    Environment, WorkspaceStatus, Permission,
)

class TestWorkspaceModels:
    def test_tenant_creation(self):
        t = Tenant(name="test-tenant", environment=Environment.DEV)
        assert t.tenant_id != ""
        assert t.name == "test-tenant"

    def test_workspace_creation(self):
        ws = Workspace(tenant_id="t1", name="dev-workspace", namespace="dev")
        assert ws.workspace_id != ""
        assert ws.tenant_id == "t1"

    def test_user_context(self):
        user = UserContext(user_id="u1", tenant_id="t1", workspace_id="w1",
                          permissions=[Permission.READ, Permission.WRITE])
        assert user.has_permission(Permission.READ)
        assert user.has_permission(Permission.WRITE)
        assert not user.has_permission(Permission.ADMIN)

    def test_admin_has_all_permissions(self):
        user = UserContext(user_id="admin", permissions=[Permission.ADMIN])
        assert user.has_permission(Permission.READ)
        assert user.has_permission(Permission.EXECUTE)

    def test_workspace_key_to_filter(self):
        key = WorkspaceKey(tenant_id="t1", workspace_id="w1", namespace="ns1")
        f = key.to_filter()
        assert f["tenant_id"] == "t1"
        assert f["workspace_id"] == "w1"
        assert f["namespace"] == "ns1"

    def test_namespace_creation(self):
        ns = Namespace(workspace_id="w1", name="app-ns")
        assert ns.namespace_id != ""

    def test_workspace_status_values(self):
        assert WorkspaceStatus.ACTIVE.value == "active"
        assert WorkspaceStatus.ARCHIVED.value == "archived"

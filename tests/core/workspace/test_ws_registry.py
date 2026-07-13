"""Workspace Registry Tests."""
import pytest
from core.workspace.models import Tenant, Workspace, WorkspaceKey
from core.workspace.registry import WorkspaceRegistry
from core.workspace.exceptions import TenantNotFoundError, WorkspaceNotFoundError, CrossWorkspaceError

class TestWorkspaceRegistry:
    def test_register_and_get_tenant(self):
        reg = WorkspaceRegistry()
        t = Tenant(name="t1")
        reg.register_tenant(t)
        assert reg.tenant_count == 1
        assert reg.get_tenant(t.tenant_id).name == "t1"

    def test_get_nonexistent_tenant_raises(self):
        reg = WorkspaceRegistry()
        with pytest.raises(TenantNotFoundError):
            reg.get_tenant("nonexistent")

    def test_register_and_get_workspace(self):
        reg = WorkspaceRegistry()
        ws = Workspace(tenant_id="t1", name="ws1")
        reg.register_workspace(ws)
        assert reg.workspace_count == 1

    def test_list_workspaces_by_tenant(self):
        reg = WorkspaceRegistry()
        reg.register_workspace(Workspace(tenant_id="t1", name="ws1"))
        reg.register_workspace(Workspace(tenant_id="t2", name="ws2"))
        assert len(reg.list_workspaces("t1")) == 1

    def test_archive_workspace(self):
        reg = WorkspaceRegistry()
        ws = Workspace(tenant_id="t1", name="ws1")
        reg.register_workspace(ws)
        reg.archive_workspace(ws.workspace_id)
        from core.workspace.models import WorkspaceStatus
        assert ws.status == WorkspaceStatus.ARCHIVED

    def test_validate_key(self):
        reg = WorkspaceRegistry()
        t = Tenant(name="t1")
        reg.register_tenant(t)
        ws = Workspace(tenant_id=t.tenant_id, name="ws1")
        reg.register_workspace(ws)
        key = WorkspaceKey(tenant_id=t.tenant_id, workspace_id=ws.workspace_id)
        reg.validate_key(key)  # should not raise

    def test_cross_workspace_error(self):
        reg = WorkspaceRegistry()
        key1 = WorkspaceKey(workspace_id="w1")
        key2 = WorkspaceKey(workspace_id="w2")
        with pytest.raises(CrossWorkspaceError):
            reg.ensure_same_workspace(key1, key2)

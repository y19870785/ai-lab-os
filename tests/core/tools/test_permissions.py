import pytest
from core.tools.permissions import PermissionManager
from core.tools.models import ToolInfo, ToolPermission
from core.tools.exceptions import ToolPermissionDeniedError


class TestPermissionManager:
    def test_no_permissions_needed(self):
        pm = PermissionManager()
        info = ToolInfo(name="echo", permissions=[])
        pm.check(info)  # should not raise

    def test_has_permission(self):
        pm = PermissionManager(agent_permissions=["read", "write"])
        info = ToolInfo(name="db", permissions=[ToolPermission.READ])
        pm.check(info)  # should not raise

    def test_lacks_permission(self):
        pm = PermissionManager(agent_permissions=["read"])
        info = ToolInfo(name="db", permissions=[ToolPermission.WRITE])
        with pytest.raises(ToolPermissionDeniedError):
            pm.check(info)

    def test_has_permission_method(self):
        pm = PermissionManager(agent_permissions=["read", "write"])
        info = ToolInfo(name="db", permissions=[ToolPermission.READ])
        assert pm.has_permission(info) is True

    def test_has_permission_false(self):
        pm = PermissionManager(agent_permissions=["read"])
        info = ToolInfo(name="db", permissions=[ToolPermission.WRITE])
        assert pm.has_permission(info) is False

    def test_set_agent_permissions(self):
        pm = PermissionManager()
        pm.set_agent_permissions(["read", "system"])
        info = ToolInfo(name="cmd", permissions=[ToolPermission.SYSTEM])
        pm.check(info)  # should now pass

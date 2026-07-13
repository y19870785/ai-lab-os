import pytest
from core.tools.models import (
    ToolInfo, ToolRequest, ToolResult, ToolStatus,
    ToolCategory, ToolPermission, ParameterSchema,
)


class TestToolInfo:
    def test_defaults(self):
        info = ToolInfo(name="test", description="A test tool")
        assert info.name == "test"
        assert info.description == "A test tool"
        assert info.version == "1.0.0"
        assert info.category == ToolCategory.UTILITY
        assert info.status == ToolStatus.REGISTERED
        assert info.timeout == 30

    def test_auto_id(self):
        a = ToolInfo(name="a")
        b = ToolInfo(name="b")
        assert a.id != b.id

    def test_permissions(self):
        info = ToolInfo(
            name="db",
            permissions=[ToolPermission.READ, ToolPermission.WRITE],
        )
        assert ToolPermission.READ in info.permissions
        assert ToolPermission.WRITE in info.permissions

    def test_parameters(self):
        schema = ParameterSchema(
            properties={"x": {"type": "integer"}},
            required=["x"],
        )
        info = ToolInfo(name="math", parameters=schema)
        assert info.parameters.properties["x"]["type"] == "integer"
        assert "x" in info.parameters.required


class TestToolRequest:
    def test_defaults(self):
        req = ToolRequest(tool_name="echo")
        assert req.tool_name == "echo"
        assert req.arguments == {}
        assert req.session_id == ""
        assert req.agent_id == ""

    def test_with_args(self):
        req = ToolRequest(
            tool_name="calc",
            arguments={"expr": "2+2"},
            agent_id="agent-1",
            session_id="sess-1",
        )
        assert req.arguments["expr"] == "2+2"
        assert req.agent_id == "agent-1"


class TestToolResult:
    def test_default_failure(self):
        r = ToolResult()
        assert r.success is False

    def test_success(self):
        r = ToolResult(success=True, output=42, latency_ms=5.0)
        assert r.success is True
        assert r.output == 42
        assert r.latency_ms == 5.0

    def test_error(self):
        r = ToolResult(success=False, error="something broke")
        assert r.error == "something broke"


class TestToolStatus:
    def test_values(self):
        assert ToolStatus.REGISTERED.value == "registered"
        assert ToolStatus.READY.value == "ready"
        assert ToolStatus.RUNNING.value == "running"
        assert ToolStatus.FAILED.value == "failed"
        assert ToolStatus.DISABLED.value == "disabled"


class TestToolCategory:
    def test_values(self):
        assert ToolCategory.UTILITY.value == "utility"
        assert ToolCategory.DATA.value == "data"
        assert ToolCategory.NETWORK.value == "network"

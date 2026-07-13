import pytest
from core.tools.adapters.mcp import MCPConverter, MCPToolInfo, MCPToolSchema, MCPToolCall, MCPToolResult
from core.tools.models import ToolRequest, ToolCategory


class TestMCPConverter:
    def test_tool_info_conversion(self):
        mcp_tool = MCPToolInfo(
            name="search", description="Search tool", server_name="my-server",
            input_schema=MCPToolSchema(
                properties={"q": {"type": "string"}},
                required=["q"],
            ),
        )
        ti = MCPConverter.mcp_tool_to_tool_info(mcp_tool)
        assert ti.name == "mcp.my-server.search"
        assert ti.category == ToolCategory.EXTERNAL
        assert "mcp" in ti.tags
        assert "my-server" in ti.tags
        assert ti.parameters.properties["q"]["type"] == "string"
        assert "q" in ti.parameters.required
        assert ti.metadata["adapter"] == "mcp"

    def test_request_conversion(self):
        req = ToolRequest(
            tool_name="mcp.s.search",
            arguments={"q": "hello"},
            trace_id="trace-123",
        )
        call = MCPConverter.tool_request_to_mcp_call(req)
        assert call.tool_name == "mcp.s.search"
        assert call.arguments == {"q": "hello"}
        assert call.call_id == "trace-123"

    def test_result_success(self):
        mcp_result = MCPToolResult(success=True, content="found it")
        result = MCPConverter.mcp_result_to_tool_result(mcp_result)
        assert result.success is True
        assert result.output == "found it"
        assert result.error is None

    def test_result_failure(self):
        mcp_result = MCPToolResult(success=False, error="timeout")
        result = MCPConverter.mcp_result_to_tool_result(mcp_result)
        assert result.success is False
        assert result.error == "timeout"

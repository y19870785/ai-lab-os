import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.tools.adapters.mcp.mock import create_mock_mcp_server


class TestMockMCPServer:
    async def test_default_tools(self):
        client = create_mock_mcp_server("test-mock")
        await client.initialize()
        tools = await client.discover_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"weather", "search"}

    async def test_invoke_default_tool(self):
        client = create_mock_mcp_server("invoke-mock")
        await client.initialize()
        from core.tools.adapters.mcp.models import MCPToolCall
        result = await client.invoke_tool(MCPToolCall(
            tool_name="weather", arguments={"query": "Tokyo"},
        ))
        assert result.success
        assert "[weather]" in result.content
        assert "Tokyo" in result.content

    async def test_custom_tools(self):
        client = create_mock_mcp_server("custom", tools=[
            ("add", "Addition", "math"),
            ("sub", "Subtraction", "math"),
        ])
        await client.initialize()
        tools = await client.discover_tools()
        assert len(tools) == 2
        assert {t.name for t in tools} == {"add", "sub"}

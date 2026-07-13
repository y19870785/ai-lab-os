import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.tools.adapters.mcp import MCPClient, MCPServerInfo, MCPToolInfo, MCPToolSchema

class TestMCPClient:
    def _make_client(self, name="test-server"):
        return MCPClient(MCPServerInfo(name=name))

    async def test_initialize_and_shutdown(self):
        c = self._make_client()
        assert await c.health_check() is False
        await c.initialize()
        assert await c.health_check() is True
        await c.shutdown()
        assert await c.health_check() is False

    async def test_register_and_discover(self):
        c = self._make_client()
        await c.initialize()
        info = MCPToolInfo(name="echo", description="Echo tool",
                           input_schema=MCPToolSchema(properties={"text": {"type": "string"}}, required=["text"]))
        c.register_tool(info, lambda args: args.get("text", ""))
        tools = await c.discover_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

    async def test_invoke_success(self):
        c = self._make_client()
        await c.initialize()
        c.register_tool(
            MCPToolInfo(name="add", description="Add"),
            lambda args: args["a"] + args["b"],
        )
        from core.tools.adapters.mcp.models import MCPToolCall
        result = await c.invoke_tool(MCPToolCall(tool_name="add", arguments={"a": 1, "b": 2}))
        assert result.success is True
        assert result.content == 3

    async def test_invoke_nonexistent(self):
        c = self._make_client()
        await c.initialize()
        from core.tools.adapters.mcp.models import MCPToolCall
        result = await c.invoke_tool(MCPToolCall(tool_name="nope"))
        assert result.success is False
        assert "not found" in str(result.error).lower()

    async def test_invoke_before_init(self):
        c = self._make_client()
        from core.tools.adapters.mcp.models import MCPToolCall
        from core.tools.adapters.mcp.exceptions import MCPConnectionError
        with pytest.raises(MCPConnectionError):
            await c.invoke_tool(MCPToolCall(tool_name="x"))

    async def test_capabilities(self):
        c = self._make_client()
        await c.initialize()
        caps = await c.get_capabilities()
        assert caps.tools is False  # no tools registered yet
        c.register_tool(MCPToolInfo(name="t"), lambda a: "ok")
        caps = await c.get_capabilities()
        assert caps.tools is True

    async def test_unregister_tool(self):
        c = self._make_client()
        await c.initialize()
        c.register_tool(MCPToolInfo(name="temp"), lambda a: "ok")
        assert c.unregister_tool("temp") is True
        assert c.unregister_tool("temp") is False
        tools = await c.discover_tools()
        assert len(tools) == 0

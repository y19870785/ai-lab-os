import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.tools.registry import ToolRegistry
from core.tools.adapters.mcp import (
    MCPClient, MCPServerInfo, MCPToolInfo, MCPToolSchema, MCPToolRegistry, MCPToolWrapper,
)

class TestMCPToolRegistry:
    async def test_add_server_and_discover(self):
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        client = MCPClient(MCPServerInfo(name="s1"))
        await client.initialize()
        client.register_tool(
            MCPToolInfo(name="echo", description="Echo",
                        input_schema=MCPToolSchema(properties={"msg": {"type": "string"}}, required=["msg"])),
            lambda args: f"echo: {args['msg']}",
        )
        await mcp_reg.add_server(client)
        assert "s1" in mcp_reg.list_servers()
        tools = mcp_reg.list_tools("s1")
        assert len(tools) == 1
        assert tools[0].name == "echo"

    async def test_tools_registered_in_tool_registry(self):
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        client = MCPClient(MCPServerInfo(name="s2"))
        client.register_tool(
            MCPToolInfo(name="search", description="Search"),
            lambda args: f"found: {args['q']}",
        )
        await mcp_reg.add_server(client)
        assert tr.exists("mcp.s2.search")
        tool = tr.get("mcp.s2.search")
        from core.tools.models import ToolRequest
        result = await tool.execute(ToolRequest(tool_name="mcp.s2.search", arguments={"q": "test"}))
        assert result.success is True
        assert "found: test" in str(result.output)

    async def test_remove_server(self):
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        client = MCPClient(MCPServerInfo(name="s3"))
        client.register_tool(MCPToolInfo(name="t1"), lambda a: "ok")
        await mcp_reg.add_server(client)
        assert tr.exists("mcp.s3.t1")
        await mcp_reg.remove_server("s3")
        assert not tr.exists("mcp.s3.t1")
        assert mcp_reg.list_servers() == []

    async def test_multiple_servers(self):
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        for i in range(3):
            c = MCPClient(MCPServerInfo(name=f"s{i}"))
            c.register_tool(MCPToolInfo(name=f"tool{i}"), lambda a, idx=i: f"result{idx}")
            await mcp_reg.add_server(c)
        assert len(mcp_reg.list_servers()) == 3
        assert len(mcp_reg.list_tools()) == 3
        assert tr.exists("mcp.s0.tool0")
        assert tr.exists("mcp.s2.tool2")

    async def test_shutdown_all(self):
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        for i in range(2):
            c = MCPClient(MCPServerInfo(name=f"s{i}"))
            c.register_tool(MCPToolInfo(name=f"t{i}"), lambda a: "ok")
            await mcp_reg.add_server(c)
        await mcp_reg.shutdown_all()
        assert mcp_reg.list_servers() == []
        assert not tr.exists("mcp.s0.t0")

    async def test_wrapper_toolprotocol(self):
        client = MCPClient(MCPServerInfo(name="wrap"))
        await client.initialize()
        mcp_tool = MCPToolInfo(name="greet", description="Greet",
                               input_schema=MCPToolSchema(properties={"name": {"type": "string"}}, required=["name"]))
        client.register_tool(mcp_tool, lambda args: f"Hello, {args['name']}!")
        wrapper = MCPToolWrapper(client=client, mcp_tool=mcp_tool)
        from core.tools.models import ToolRequest
        result = await wrapper.execute(ToolRequest(tool_name="greet", arguments={"name": "World"}))
        assert result.success is True
        assert result.output == "Hello, World!"
        assert await wrapper.health_check() is True

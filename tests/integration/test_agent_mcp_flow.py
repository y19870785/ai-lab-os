import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.tools.registry import ToolRegistry
from core.tools.executor import ToolExecutor
from core.tools.adapters.mcp import (
    MCPClient, MCPServerInfo, MCPToolInfo, MCPToolSchema,
    MCPToolRegistry, MCPToolWrapper, create_mock_mcp_server,
)
from core.tools.models import ToolRequest
from core.agents.models import AgentInfo, AgentRequest, AgentContext
from core.agents.executor import AgentExecutor


class TestAgentMCPFlow:
    """Agent -> ToolExecutor -> MCP Adapter -> Mock MCP Server ????"""

    async def test_mcp_tool_through_tool_executor(self):
        # 1. ?? MCP Server ?????
        client = await self._setup_mcp_server("weather-srv")
        # 2. ??? ToolRegistry
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        await mcp_reg.add_server(client)
        # 3. ?? ToolExecutor ??
        from core.tools.permissions import PermissionManager
        pm = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=tr, permission_manager=pm)
        result = await te.execute_by_name(
            "mcp.weather-srv.weather",
            arguments={"query": "Beijing"},
        )
        assert result.success is True
        assert "[weather]" in str(result.output)
        assert "Beijing" in str(result.output)

    async def test_agent_calls_mcp_tool(self):
        client = await self._setup_mcp_server("search-srv")
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        await mcp_reg.add_server(client)
        from core.tools.permissions import PermissionManager
        pm2 = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=tr, permission_manager=pm2)
        info = AgentInfo(name="mcp-agent", description="MCP test")
        executor = AgentExecutor(info=info, tool_registry=tr)
        executor._tool_executor = te
        ctx = AgentContext(session_id="s-mcp", agent_id=info.id)
        ctx.variables = {"tool_calls": [{
            "name": "mcp.search-srv.search",
            "arguments": {"query": "AI papers"},
        }]}
        req = AgentRequest(user_input="search AI", session_id="s-mcp", tools_enabled=True)
        tools = await executor._invoke_tools(req, ctx)
        assert len(tools) == 1
        assert tools[0].success is True
        assert "[search]" in tools[0].result
        assert "AI papers" in tools[0].result

    async def test_mcp_multiple_tools_one_server(self):
        client = MCPClient(MCPServerInfo(name="multi"))
        client.register_tool(
            MCPToolInfo(name="translate", description="Translate",
                        input_schema=MCPToolSchema(properties={"text": {"type": "string"}}, required=["text"])),
            lambda args: f"translated: {args['text']}",
        )
        client.register_tool(
            MCPToolInfo(name="summarize", description="Summarize",
                        input_schema=MCPToolSchema(properties={"doc": {"type": "string"}}, required=["doc"])),
            lambda args: f"summary of: {args['doc']}",
        )
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        await mcp_reg.add_server(client)
        from core.tools.permissions import PermissionManager
        pm3 = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=tr, permission_manager=pm3)
        r1 = await te.execute_by_name("mcp.multi.translate", arguments={"text": "hello"})
        r2 = await te.execute_by_name("mcp.multi.summarize", arguments={"doc": "long text"})
        assert r1.success and "translated" in str(r1.output)
        assert r2.success and "summary" in str(r2.output)

    async def test_mcp_tool_not_found(self):
        client = await self._setup_mcp_server("srv-x")
        tr = ToolRegistry()
        mcp_reg = MCPToolRegistry(tr)
        await mcp_reg.add_server(client)
        from core.tools.permissions import PermissionManager
        pm = PermissionManager(agent_permissions=["execute"])
        te = ToolExecutor(registry=tr, permission_manager=pm)
        result = await te.execute_by_name("mcp.srv-x.nonexistent", arguments={})
        assert result.success is False

    async def _setup_mcp_server(self, name: str) -> MCPClient:
        client = MCPClient(MCPServerInfo(name=name))
        await client.initialize()
        client.register_tool(
            MCPToolInfo(name="weather" if "weather" in name else "search",
                        description="Mock tool",
                        input_schema=MCPToolSchema(
                            properties={"query": {"type": "string"}},
                            required=["query"],
                        )),
            lambda args: f"[{'weather' if 'weather' in name else 'search'}] Result for: {args['query']}",
        )
        return client

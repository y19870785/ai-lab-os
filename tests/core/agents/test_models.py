import pytest
from core.agents.models import AgentInfo, AgentRequest, AgentResponse, AgentContext, AgentStatus, ToolCallRecord

class TestAgentModels:
    def test_agent_info_defaults(self):
        info = AgentInfo(name="test")
        assert info.name == "test"
        assert info.id
        assert len(info.id) == 32
        assert info.status == AgentStatus.CREATED
        assert info.version == "1.0.0"
    def test_agent_request_defaults(self):
        req = AgentRequest(user_input="hello")
        assert req.memory_enabled is True
        assert req.knowledge_enabled is True
        assert req.tools_enabled is True
        assert req.stream is False
    def test_agent_response_defaults(self):
        resp = AgentResponse(answer="hi")
        assert resp.answer == "hi"
        assert resp.status == "ok"
        assert resp.tool_calls == []
    def test_agent_context_defaults(self):
        ctx = AgentContext()
        assert ctx.session_id == ""
        assert ctx.memory_items == []
        assert ctx.knowledge_results == []
    def test_agent_status_values(self):
        assert AgentStatus.CREATED.value == "created"
        assert AgentStatus.READY.value == "ready"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.DESTROYED.value == "destroyed"
    def test_tool_call_record(self):
        tc = ToolCallRecord(tool_name="search", arguments={"q": "test"})
        assert tc.tool_name == "search"
        assert tc.arguments == {"q": "test"}
        assert tc.error is None
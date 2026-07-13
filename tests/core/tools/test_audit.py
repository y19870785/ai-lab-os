import pytest
from core.tools.audit import ToolAuditLogger
from core.tools.models import ToolInfo, ToolRequest, ToolResult


class TestToolAudit:
    def _make_logger(self):
        return ToolAuditLogger()

    def test_record_single(self):
        logger = self._make_logger()
        info = ToolInfo(name="test")
        req = ToolRequest(tool_name="test", arguments={"x": 1}, agent_id="a1")
        result = ToolResult(success=True, latency_ms=5.0)
        logger.record(info, req, result)
        records = logger.get_records()
        assert len(records) == 1
        assert records[0]["tool_name"] == "test"
        assert records[0]["agent_id"] == "a1"
        assert records[0]["success"] is True

    def test_record_failure(self):
        logger = self._make_logger()
        info = ToolInfo(name="fail")
        req = ToolRequest(tool_name="fail", agent_id="a2")
        result = ToolResult(success=False, error="boom")
        logger.record(info, req, result)
        records = logger.get_records()
        assert records[0]["error"] == "boom"

    def test_query_by_tool(self):
        logger = self._make_logger()
        logger.record(ToolInfo(name="a"), ToolRequest(tool_name="a"), ToolResult(success=True))
        logger.record(ToolInfo(name="b"), ToolRequest(tool_name="b"), ToolResult(success=True))
        results = logger.query(tool_name="a")
        assert len(results) == 1
        assert results[0]["tool_name"] == "a"

    def test_query_by_agent(self):
        logger = self._make_logger()
        logger.record(ToolInfo(name="x"), ToolRequest(tool_name="x", agent_id="agent-1"), ToolResult(success=True))
        logger.record(ToolInfo(name="y"), ToolRequest(tool_name="y", agent_id="agent-2"), ToolResult(success=True))
        results = logger.query(agent_id="agent-1")
        assert len(results) == 1

    def test_record_count(self):
        logger = self._make_logger()
        logger.record(ToolInfo(name="a"), ToolRequest(tool_name="a"), ToolResult(success=True))
        logger.record(ToolInfo(name="b"), ToolRequest(tool_name="b"), ToolResult(success=True))
        assert logger.record_count == 2

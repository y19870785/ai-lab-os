import pytest
from core.tools.metrics import ToolMetricsCollector


class TestToolMetrics:
    def test_record_success(self):
        mc = ToolMetricsCollector()
        mc.record("echo", success=True, latency_ms=10.0)
        snap = mc.snapshot()
        assert snap["echo"]["call_count"] == 1
        assert snap["echo"]["success_rate"] == 1.0

    def test_record_failure(self):
        mc = ToolMetricsCollector()
        mc.record("echo", success=False, latency_ms=5.0)
        snap = mc.snapshot()
        assert snap["echo"]["success_rate"] == 0.0

    def test_record_timeout(self):
        mc = ToolMetricsCollector()
        mc.record("echo", success=False, latency_ms=100, timeout=True)
        snap = mc.snapshot()
        assert snap["echo"]["timeout_count"] == 1

    def test_avg_latency(self):
        mc = ToolMetricsCollector()
        mc.record("echo", success=True, latency_ms=10.0)
        mc.record("echo", success=True, latency_ms=20.0)
        snap = mc.snapshot()
        assert snap["echo"]["avg_latency_ms"] == 15.0

    def test_clear(self):
        mc = ToolMetricsCollector()
        mc.record("echo", success=True, latency_ms=1.0)
        mc.clear()
        assert mc.snapshot() == {}

    def test_multiple_tools(self):
        mc = ToolMetricsCollector()
        mc.record("a", success=True, latency_ms=1.0)
        mc.record("b", success=False, latency_ms=2.0)
        snap = mc.snapshot()
        assert len(snap) == 2
        assert snap["a"]["call_count"] == 1
        assert snap["b"]["call_count"] == 1

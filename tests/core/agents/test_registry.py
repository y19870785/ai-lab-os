import pytest
from core.agents import AgentRegistry, AgentInfo, AgentNotFoundError

class TestAgentRegistry:
    def test_register_and_get(self):
        reg = AgentRegistry()
        info = AgentInfo(id="a1", name="test")
        reg.register(info)
        assert reg.exists("a1")
        assert reg.count == 1
    def test_get_returns_info(self):
        reg = AgentRegistry()
        info = AgentInfo(id="a1", name="test", capabilities=["search"])
        reg.register(info)
        got = reg.get("a1")
        assert got.name == "test"
        assert "search" in got.capabilities
    def test_get_nonexistent_raises(self):
        reg = AgentRegistry()
        with pytest.raises(AgentNotFoundError):
            reg.get("nope")
    def test_unregister(self):
        reg = AgentRegistry()
        info = AgentInfo(id="a1", name="test")
        reg.register(info)
        assert reg.unregister("a1")
        assert not reg.exists("a1")
    def test_list(self):
        reg = AgentRegistry()
        reg.register(AgentInfo(id="a"))
        reg.register(AgentInfo(id="b"))
        assert len(reg.list()) == 2
    def test_find_by_capability(self):
        reg = AgentRegistry()
        reg.register(AgentInfo(id="a", capabilities=["search"]))
        reg.register(AgentInfo(id="b", capabilities=["summarize"]))
        results = reg.find_by_capability("search")
        assert len(results) == 1
        assert results[0].id == "a"
    def test_find_by_name(self):
        reg = AgentRegistry()
        reg.register(AgentInfo(id="a", name="analyst"))
        reg.register(AgentInfo(id="b", name="analyst"))
        assert len(reg.find_by_name("analyst")) == 2
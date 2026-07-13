import pytest
from core.tools.registry import ToolRegistry
from core.tools.models import ToolInfo, ToolCategory
from core.tools.exceptions import ToolNotFoundError


def _make_info(name="test", category=ToolCategory.UTILITY, tags=None):
    return ToolInfo(name=name, category=category, tags=tags or [])


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        info = _make_info("echo")
        reg.register(info, lambda: None)
        assert reg.exists("echo")
        assert reg.get_info("echo").name == "echo"

    def test_list(self):
        reg = ToolRegistry()
        reg.register(_make_info("a"), lambda: None)
        reg.register(_make_info("b"), lambda: None)
        assert len(reg.list()) == 2
        assert reg.count == 2

    def test_unregister(self):
        reg = ToolRegistry()
        reg.register(_make_info("temp"), lambda: None)
        assert reg.unregister("temp") is True
        assert not reg.exists("temp")

    def test_unregister_nonexistent(self):
        reg = ToolRegistry()
        assert reg.unregister("nope") is False

    def test_get_nonexistent_raises(self):
        reg = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            reg.get_info("nope")

    def test_search_by_category(self):
        reg = ToolRegistry()
        reg.register(_make_info("a", ToolCategory.UTILITY), lambda: None)
        reg.register(_make_info("b", ToolCategory.DATA), lambda: None)
        results = reg.search(category="data")
        assert len(results) == 1
        assert results[0].name == "b"

    def test_search_by_tag(self):
        reg = ToolRegistry()
        reg.register(_make_info("a", tags=["test", "fast"]), lambda: None)
        reg.register(_make_info("b", tags=["slow"]), lambda: None)
        results = reg.search(tag="test")
        assert len(results) == 1
        assert results[0].name == "a"

    def test_search_by_name_pattern(self):
        reg = ToolRegistry()
        reg.register(_make_info("calculator"), lambda: None)
        reg.register(_make_info("echo"), lambda: None)
        results = reg.search(name_pattern="calc")
        assert len(results) == 1
        assert results[0].name == "calculator"

    def test_list_names(self):
        reg = ToolRegistry()
        reg.register(_make_info("x"), lambda: None)
        reg.register(_make_info("y"), lambda: None)
        names = reg.list_names()
        assert "x" in names
        assert "y" in names

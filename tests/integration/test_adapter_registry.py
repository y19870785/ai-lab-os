import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")
from core.tools.adapters.registry import AdapterRegistry
from core.tools.adapters.protocol import ToolAdapterProtocol


class _MockAdapter(ToolAdapterProtocol):
    def __init__(self, name="mock-adapter"):
        self._name = name
        self._init_called = False
        self._shutdown_called = False
    async def initialize(self): self._init_called = True
    async def shutdown(self): self._shutdown_called = True
    async def discover(self): return [{"name": "tool1"}, {"name": "tool2"}]
    async def health(self): return True
    @property
    def name(self): return self._name


class TestAdapterRegistry:
    async def test_register_and_get(self):
        reg = AdapterRegistry()
        a = _MockAdapter("a1")
        reg.register(a)
        assert reg.get("a1") is a
        assert reg.count == 1

    async def test_unregister(self):
        reg = AdapterRegistry()
        a = _MockAdapter("temp")
        reg.register(a)
        assert reg.unregister("temp") is True
        assert reg.unregister("temp") is False

    async def test_initialize_all(self):
        reg = AdapterRegistry()
        a1 = _MockAdapter("a1")
        a2 = _MockAdapter("a2")
        reg.register(a1)
        reg.register(a2)
        await reg.initialize_all()
        assert a1._init_called and a2._init_called

    async def test_shutdown_all(self):
        reg = AdapterRegistry()
        a1 = _MockAdapter("a1")
        a2 = _MockAdapter("a2")
        reg.register(a1)
        reg.register(a2)
        await reg.shutdown_all()
        assert a1._shutdown_called and a2._shutdown_called

    async def test_discover_all(self):
        reg = AdapterRegistry()
        reg.register(_MockAdapter("a1"))
        reg.register(_MockAdapter("a2"))
        results = await reg.discover_all()
        assert len(results) == 2
        assert len(results["a1"]) == 2
        assert len(results["a2"]) == 2

    async def test_list_names(self):
        reg = AdapterRegistry()
        reg.register(_MockAdapter("x"))
        reg.register(_MockAdapter("y"))
        names = reg.list_names()
        assert set(names) == {"x", "y"}

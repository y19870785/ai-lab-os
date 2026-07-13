import pytest
from core.agents import AgentLifecycleManager, AgentInfo, AgentStatus, AgentNotReadyError

class TestLifecycle:
    def test_initial_state(self):
        info = AgentInfo(name="test")
        lm = AgentLifecycleManager(info)
        assert lm.current() == AgentStatus.CREATED
    def test_valid_transition(self):
        info = AgentInfo(name="test")
        lm = AgentLifecycleManager(info)
        assert lm.transition(AgentStatus.INITIALIZED)
        assert lm.current() == AgentStatus.INITIALIZED
    def test_invalid_transition(self):
        info = AgentInfo(name="test")
        lm = AgentLifecycleManager(info)
        assert not lm.transition(AgentStatus.RUNNING)
        assert lm.current() == AgentStatus.CREATED
    def test_full_lifecycle(self):
        info = AgentInfo(name="test")
        lm = AgentLifecycleManager(info)
        assert lm.transition(AgentStatus.INITIALIZED)
        assert lm.transition(AgentStatus.READY)
        assert lm.transition(AgentStatus.RUNNING)
        assert lm.transition(AgentStatus.IDLE)
        assert lm.transition(AgentStatus.STOPPED)
        assert lm.transition(AgentStatus.DESTROYED)
        assert lm.current() == AgentStatus.DESTROYED
    def test_assert_ready_raises(self):
        info = AgentInfo(name="test")
        lm = AgentLifecycleManager(info)
        with pytest.raises(AgentNotReadyError):
            lm.assert_ready()
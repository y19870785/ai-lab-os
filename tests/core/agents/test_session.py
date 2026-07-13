import pytest
import time
from core.agents.session import AgentSession

class TestAgentSession:
    def test_session_defaults(self):
        s = AgentSession(session_id="s1", agent_id="a1")
        assert s.session_id == "s1"
        assert s.agent_id == "a1"
        assert s.active is True
        assert s.round_count == 0
        assert s.token_count == 0
    def test_add_tokens(self):
        s = AgentSession()
        s.add_tokens(100)
        assert s.token_count == 100
    def test_add_round(self):
        s = AgentSession()
        s.add_round()
        s.add_round()
        assert s.round_count == 2
    def test_elapsed_ms(self):
        s = AgentSession()
        time.sleep(0.01)
        assert s.elapsed_ms() > 0
    def test_end_session(self):
        s = AgentSession()
        assert s.active
        s.end()
        assert not s.active
        assert s.ended_at is not None
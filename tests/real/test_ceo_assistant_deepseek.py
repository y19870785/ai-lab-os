"""CEO Assistant - DeepSeek real end-to-end tests.

Only runs when OPENAI_API_KEY is configured.
Run separately: python -m pytest tests/real/ -q -m real
"""

import pytest
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest_asyncio
from dotenv import load_dotenv
load_dotenv()

pytestmark = [
    pytest.mark.real,
    pytest.mark.skipif(
        not os.getenv("OPENAI_API_KEY") or len(os.getenv("OPENAI_API_KEY", "")) < 10,
        reason="OPENAI_API_KEY not set - skip real provider tests"
    ),
]


@pytest_asyncio.fixture
async def real_app(tmp_path):
    """Create CEOAssistant with real DeepSeek LLM."""
    from applications.ceo_assistant.application import CEOAssistant
    from core.bus.bus import get_bus
    from core.memory.manager import MemoryManager
    from core.memory.models import MemoryType
    from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
    from core.memory.storage.sqlite_decision import SQLiteDecisionStore
    from core.memory.session import SessionMemory
    from core.providers.llm.openai import OpenAILLMProvider

    db_dir = str(tmp_path / "sqlite")
    os.makedirs(db_dir, exist_ok=True)

    bus = get_bus()
    await bus.start()

    memory = MemoryManager(bus=bus)
    memory.register_store(MemoryType.SESSION, SessionMemory(3600, bus=bus))
    es = SQLiteEpisodicStore(db_path=os.path.join(db_dir, "episodic.db"))
    await es.initialize()
    memory.register_store(MemoryType.EPISODIC, es)
    ds = SQLiteDecisionStore(db_path=os.path.join(db_dir, "decision.db"))
    await ds.initialize()
    memory.register_store(MemoryType.DECISION, ds)

    llm = OpenAILLMProvider(
        api_key=os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("OPENAI_BASE_URL", ""),
        model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
    )
    await llm.initialize()

    app = CEOAssistant(memory_manager=memory, llm_provider=llm)
    yield app

    await llm.shutdown()
    await bus.stop()
    await es.close()
    await ds.close()


class TestDeepSeekReal:

    @pytest.mark.asyncio
    async def test_deepseek_chat_basic(self, real_app):
        from applications.models import ApplicationRequest
        resp = await real_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="Reply in one sentence: AI-Lab is an AI operating system.",
        ))
        assert resp.status == "ok"
        assert len(resp.answer) > 0
        assert "MOCK" not in resp.answer

    @pytest.mark.asyncio
    async def test_deepseek_work_log(self, real_app):
        from applications.models import ApplicationRequest
        resp = await real_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="Record: Confirmed bee wax bag testing plan with Manager Zhang.",
        ))
        assert resp.status == "ok"
        assert len(resp.answer) > 0

    @pytest.mark.asyncio
    async def test_deepseek_task(self, real_app):
        from applications.models import ApplicationRequest
        resp = await real_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="Remind me to complete the FDA report tomorrow.",
        ))
        assert resp.status == "ok"

    @pytest.mark.asyncio
    async def test_deepseek_decision(self, real_app):
        from applications.models import ApplicationRequest
        resp = await real_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="Decide to use DeepSeek as default LLM provider.",
        ))
        assert resp.status == "ok"

    @pytest.mark.asyncio
    async def test_deepseek_brief(self, real_app):
        from applications.models import ApplicationRequest
        await real_app.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="Remind me to complete DeepSeek validation report.",
        ))
        brief = await real_app._handle_brief(ApplicationRequest(
            application_name="ceo-assistant", user_input="brief",
        ))
        assert brief["status"] == "ok"
        assert len(brief["answer"]) > 0
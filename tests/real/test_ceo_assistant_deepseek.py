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
    """Create CEOAssistant through the real Composition Root."""
    from core.system import SystemSettings, create_system

    settings = SystemSettings(
        environment="test-real",
        provider_mode="real",
        data_dir=tmp_path,
        sqlite_dir=tmp_path / "sqlite",
        api_key=os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        base_url=os.getenv("AI_LAB_LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", ""),
        model=os.getenv("AI_LAB_LLM_MODEL") or os.getenv("OPENAI_MODEL", ""),
    )
    system = await create_system(settings)
    await system.start()
    try:
        yield system.ceo_assistant
    finally:
        await system.shutdown()


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

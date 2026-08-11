"""CEO Assistant - DeepSeek real end-to-end tests.

Only runs with explicit two-factor authorization and an available credential.
Run separately with --run-real-provider and AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1.
"""

import pytest
import pytest_asyncio

pytestmark = pytest.mark.real


@pytest_asyncio.fixture
async def real_app(tmp_path, real_provider_environment: dict[str, str]):
    """Create CEOAssistant through the real Composition Root."""
    from core.system import SystemSettings, create_system

    settings = SystemSettings(
        environment="test-real",
        provider_mode="real",
        data_dir=tmp_path,
        sqlite_dir=tmp_path / "sqlite",
        api_key=real_provider_environment["api_key"],
        base_url=real_provider_environment["base_url"],
        model=real_provider_environment["model"],
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

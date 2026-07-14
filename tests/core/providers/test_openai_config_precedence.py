"""Provider configuration precedence and explicit-mode tests."""

import pytest

from core.providers.llm.openai import OpenAILLMProvider
from core.system import create_system, load_system_settings
from core.system.exceptions import ProviderNotConfiguredError


def test_explicit_model_wins_over_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")
    provider = OpenAILLMProvider(model="explicit-model")
    assert provider._model == "explicit-model"


def test_environment_model_wins_over_default(monkeypatch):
    monkeypatch.delenv("AI_LAB_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")
    provider = OpenAILLMProvider(model=None)
    assert provider._model == "environment-model"


def test_default_model_is_last_resort(monkeypatch):
    monkeypatch.delenv("AI_LAB_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    provider = OpenAILLMProvider(model=None)
    assert provider._model == "gpt-4o-mini"


@pytest.mark.asyncio(loop_scope="function")
async def test_missing_config_does_not_implicitly_create_mock(monkeypatch, tmp_path):
    for name in (
        "AI_LAB_PROVIDER_MODE", "AI_LAB_LLM_API_KEY", "OPENAI_API_KEY",
        "AI_LAB_LLM_BASE_URL", "OPENAI_BASE_URL", "AI_LAB_LLM_MODEL", "OPENAI_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AI_LAB_DATA_DIR", str(tmp_path))
    settings = load_system_settings(load_dotenv=False)
    assert settings.provider_mode == "invalid"
    with pytest.raises(ProviderNotConfiguredError):
        await create_system(settings)

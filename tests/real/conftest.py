"""Real Provider 测试专用的显式授权与环境准备。"""

import os

import pytest
from dotenv import load_dotenv

_AUTHORIZATION_MESSAGE = (
    "Real-provider tests require --run-real-provider and "
    "AI_LAB_ALLOW_REAL_PROVIDER_TESTS=1."
)
_CREDENTIAL_MESSAGE = "Real-provider credential is not configured."


@pytest.fixture(autouse=True)
def isolate_api_keys(monkeypatch):
    """覆盖全局 conftest 的同名 fixture。

    在 real 测试中保留环境变量，不做清除。
    """
    # 不做任何清除
    yield


@pytest.fixture(scope="session")
def real_provider_environment(pytestconfig: pytest.Config) -> dict[str, str]:
    """双授权后才加载 dotenv，并在 Provider 初始化前确认凭据可用。"""
    if not pytestconfig.getoption("--run-real-provider"):
        pytest.skip(_AUTHORIZATION_MESSAGE)
    if os.getenv("AI_LAB_ALLOW_REAL_PROVIDER_TESTS") != "1":
        pytest.skip(_AUTHORIZATION_MESSAGE)

    load_dotenv()

    api_key = os.getenv("AI_LAB_LLM_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if len(api_key) < 10 or api_key == "DISABLED":
        pytest.skip(_CREDENTIAL_MESSAGE)

    return {
        "api_key": api_key,
        "base_url": os.getenv("AI_LAB_LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL", ""),
        "model": os.getenv("AI_LAB_LLM_MODEL") or os.getenv("OPENAI_MODEL", ""),
    }

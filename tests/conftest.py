"""AI-Lab 全局测试配置。"""

import pytest
import os


def pytest_configure(config):
    """注册自定义 marker。"""
    config.addinivalue_line("markers", "real: Real Provider test (requires API key)")
    config.addinivalue_line("markers", "slow: Slow-running test")


@pytest.fixture(autouse=True)
def isolate_api_keys(monkeypatch):
    """隔离 API key 环境变量，防止 real/ 测试污染普通测试。

    对于非 real 标记的测试，清除所有 LLM API key 环境变量，
    确保 ApplicationRuntime._detect_provider_mode() 返回 'mock'。
    """
    # 检查当前测试是否有 real 标记
    # pytest 在 fixture 中可以通过 request 获取 marker
    # 但 autouse fixture 不能直接获取 request

    # 策略：用 monkeypatch 在所有测试中清除，
    # real/ 目录的 conftest 在更高层级会重新设置
    keys_to_clear = [
        "OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL",
        "AI_LAB_LLM_API_KEY", "AI_LAB_LLM_BASE_URL", "AI_LAB_LLM_MODEL",
    ]
    for key in keys_to_clear:
        if key in os.environ:
            monkeypatch.delenv(key, raising=False)

    # 标记 .env 已处理，防止 runtime.execute() 重新 load_dotenv 覆盖隔离
    monkeypatch.setenv("AI_LAB_DOTENV_LOADED", "1")

    yield
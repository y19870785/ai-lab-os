"""Real Provider 测试专用配置。

覆盖全局 conftest 的 API key 隔离。
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

HOOK_PASSED = False
_REAL_TEST_ROOT = Path(__file__).resolve().parent


def _is_real_test_item(item: pytest.Item) -> bool:
    """Return whether a collected test belongs to the real-provider tree."""
    return Path(str(item.path)).resolve().is_relative_to(_REAL_TEST_ROOT)


@pytest.fixture(autouse=True)
def isolate_api_keys(monkeypatch):
    """覆盖全局 conftest 的同名 fixture。

    在 real 测试中保留环境变量，不做清除。
    """
    # 不做任何清除
    yield


# 模块级别 skip 检查
def pytest_collection_modifyitems(config, items):
    api_key = os.getenv("OPENAI_API_KEY") or ""
    if not api_key or len(api_key) < 10:
        for item in items:
            if _is_real_test_item(item):
                item.add_marker(pytest.mark.skip(reason="API key not configured"))

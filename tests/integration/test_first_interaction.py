"""首次交互集成测试。

验证 CLI 与 CEO Assistant 的集成链路。
使用 Mock 模式，不依赖真实 API。
"""

import pytest
import asyncio
import os
import sys
from io import StringIO


@pytest.mark.asyncio
async def test_ceo_command_registered():
    """验证 ceo 命令已在 CLI 中注册。"""
    from cli.main import COMMANDS
    assert "ceo" in COMMANDS


def test_detect_provider_mode_mock():
    """验证显式 mock 模式。"""
    # 备份原环境变量
    old_key = os.environ.pop("OPENAI_API_KEY", None)
    old_url = os.environ.pop("OPENAI_BASE_URL", None)
    old_model = os.environ.pop("OPENAI_MODEL", None)
    old_mode = os.environ.get("AI_LAB_PROVIDER_MODE")
    try:
        os.environ["AI_LAB_PROVIDER_MODE"] = "mock"
        from core.provider_mode import detect_provider_mode
        assert detect_provider_mode() == "mock"
    finally:
        if old_mode is not None:
            os.environ["AI_LAB_PROVIDER_MODE"] = old_mode
        else:
            os.environ.pop("AI_LAB_PROVIDER_MODE", None)
        if old_key:
            os.environ["OPENAI_API_KEY"] = old_key
        if old_url:
            os.environ["OPENAI_BASE_URL"] = old_url
        if old_model:
            os.environ["OPENAI_MODEL"] = old_model


def test_detect_provider_mode_real():
    """验证 provider mode 检测在有完整配置时返回 real。"""
    old_key = os.environ.get("OPENAI_API_KEY")
    old_url = os.environ.get("OPENAI_BASE_URL")
    old_model = os.environ.get("OPENAI_MODEL")
    old_mode = os.environ.pop("AI_LAB_PROVIDER_MODE", None)
    try:
        os.environ["OPENAI_API_KEY"] = "sk-" + "test1234567890abcdef"
        os.environ["OPENAI_BASE_URL"] = "https://api.test.com/v1"
        os.environ["OPENAI_MODEL"] = "test-model"
        from core.provider_mode import detect_provider_mode
        assert detect_provider_mode() == "real"
    finally:
        if old_key:
            os.environ["OPENAI_API_KEY"] = old_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        if old_url:
            os.environ["OPENAI_BASE_URL"] = old_url
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
        if old_model:
            os.environ["OPENAI_MODEL"] = old_model
        else:
            os.environ.pop("OPENAI_MODEL", None)
        if old_mode:
            os.environ["AI_LAB_PROVIDER_MODE"] = old_mode


def test_detect_provider_mode_invalid():
    """验证 provider mode 检测在配置不完整时返回 invalid。"""
    old_key = os.environ.get("OPENAI_API_KEY")
    old_url = os.environ.get("OPENAI_BASE_URL")
    old_model = os.environ.get("OPENAI_MODEL")
    old_mode = os.environ.pop("AI_LAB_PROVIDER_MODE", None)
    try:
        os.environ["OPENAI_API_KEY"] = "sk-" + "test1234567890abcdef"
        os.environ.pop("OPENAI_BASE_URL", None)
        os.environ.pop("OPENAI_MODEL", None)
        from core.provider_mode import detect_provider_mode
        assert detect_provider_mode() == "invalid"
    finally:
        if old_key:
            os.environ["OPENAI_API_KEY"] = old_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        if old_url:
            os.environ["OPENAI_BASE_URL"] = old_url
        else:
            os.environ.pop("OPENAI_BASE_URL", None)
        if old_model:
            os.environ["OPENAI_MODEL"] = old_model
        else:
            os.environ.pop("OPENAI_MODEL", None)
        if old_mode:
            os.environ["AI_LAB_PROVIDER_MODE"] = old_mode


def test_ceo_module_importable():
    """验证 ceo 模块可导入。"""
    from cli.ceo import run_ceo, _detect_intent, _handle_command
    assert callable(run_ceo)
    assert callable(_detect_intent)
    assert callable(_handle_command)

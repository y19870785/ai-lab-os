"""交互式 CEO CLI 测试。

验证：命令解析、意图路由、help/status/exit、无效命令处理。
注意：这些测试测试 CLI 逻辑本身，不依赖真实应用或 LLM。
"""

import pytest
import asyncio
import os


# ---- 意图路由测试 ----

def test_intent_brief():
    from cli.ceo import _detect_intent
    assert _detect_intent("今日简报") == "brief"


def test_intent_decision():
    from cli.ceo import _detect_intent
    assert _detect_intent("决定先做21 CFR 175.300") == "decision"
    assert _detect_intent("我选择方案A") == "decision"


def test_intent_task():
    from cli.ceo import _detect_intent
    assert _detect_intent("提醒我明天下午跟进") == "task"
    assert _detect_intent("todo 买咖啡") == "task"


def test_intent_knowledge():
    from cli.ceo import _detect_intent
    assert _detect_intent("什么是FDA标准") == "knowledge"
    assert _detect_intent("解释一下21 CFR") == "knowledge"


def test_intent_work_log():
    from cli.ceo import _detect_intent
    assert _detect_intent("今天和张经理确认了蜂蜡检测方案") == "work_log"
    assert _detect_intent("今天见了张经理讨论蜂蜡方案") == "work_log"


def test_intent_command():
    from cli.ceo import _detect_intent
    assert _detect_intent("/help") == "command"
    assert _detect_intent("/exit") == "command"


def test_intent_chat_fallback():
    from cli.ceo import _detect_intent
    assert _detect_intent("你好") == "chat"
    assert _detect_intent("谢谢") == "chat"


# ---- 命令处理测试 ----

@pytest.mark.asyncio
async def test_help_command():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "help", "")
    assert result is not None
    assert "/help" in result
    assert "/exit" in result


@pytest.mark.asyncio
async def test_exit_command():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "exit", "")
    assert result is None


@pytest.mark.asyncio
async def test_quit_command():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "quit", "")
    assert result is None


@pytest.mark.asyncio
async def test_unknown_command():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "nonexistent", "")
    assert "nonexistent" in result.lower() or "cmd" in result.lower()


@pytest.mark.asyncio
async def test_clear_command():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "clear", "")
    assert result == ""


@pytest.mark.asyncio
async def test_knowledge_without_args():
    from cli.ceo import _handle_command
    result = await _handle_command(None, "knowledge", "")
    assert result is not None

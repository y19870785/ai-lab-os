"""CEO Assistant —— 意图路由测试。

验证 _detect_intent 在各种输入下的正确性。
优先级：decision > task > work_log > knowledge > chat
"""

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from applications.ceo_assistant.application import CEOAssistant
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION


@pytest.fixture
def app():
    """创建不含依赖的 CEOAssistant 用于纯逻辑测试。"""
    return CEOAssistant(admission=PERMISSIVE_TEST_ADMISSION)


class TestIntentRouter:
    """意图识别测试。"""

    @pytest.mark.asyncio
    async def test_brief_keywords(self, app):
        """简报关键词应触发 brief 意图。"""
        for text in ["今日简报", "生成今日简报", "daily brief", "工作概览"]:
            result = await app._detect_intent(text)
            assert result["intent"] == "brief", f"输入 '{text}' 应识别为 brief"

    @pytest.mark.asyncio
    async def test_task_keywords(self, app):
        """任务关键词应触发 task 意图。"""
        for text in ["创建任务", "待办事项", "提醒我明天开会"]:
            result = await app._detect_intent(text)
            assert result["intent"] == "task", f"输入 '{text}' 应识别为 task"

    @pytest.mark.asyncio
    async def test_decision_keywords(self, app):
        """决策关键词应触发 decision 意图，优先级高于 task。"""
        for text in ["决定采用方案A", "这次选择先做检测", "确认采用此方案", "放弃了方案B"]:
            result = await app._detect_intent(text)
            assert result["intent"] == "decision", f"输入 '{text}' 应识别为 decision"

    @pytest.mark.asyncio
    async def test_work_log_keywords(self, app):
        """工作记录关键词应触发 work_log 意图。"""
        for text in ["今天和张经理确认了方案", "完成了蜂蜡检测报告"]:
            result = await app._detect_intent(text)
            assert result["intent"] == "work_log", f"输入 '{text}' 应识别为 work_log"

    @pytest.mark.asyncio
    async def test_knowledge_keywords(self, app):
        """知识问答关键词应触发 knowledge 意图。"""
        for text in ["什么是FDA检测", "解释21 CFR标准", "法规要求查询"]:
            result = await app._detect_intent(text)
            assert result["intent"] == "knowledge", f"输入 '{text}' 应识别为 knowledge"

    @pytest.mark.asyncio
    async def test_decision_over_task(self, app):
        """当同时命中 decision 和 task 关键词时，decision 优先。"""
        result = await app._detect_intent("决定创建这个任务")
        assert result["intent"] == "decision", "decision 应优先于 task"

    @pytest.mark.asyncio
    async def test_default_chat(self, app):
        """无明确关键词时默认为 chat。"""
        result = await app._detect_intent("你好")
        assert result["intent"] == "chat"

    @pytest.mark.asyncio
    async def test_english_input(self, app):
        """英文输入也能正确路由。"""
        result = await app._detect_intent("Create a new task for tomorrow")
        assert result["intent"] in ("task", "chat")  # task 因为 "task" 在输入中

    @pytest.mark.asyncio
    async def test_empty_input(self, app):
        """空输入默认为 chat。"""
        result = await app._detect_intent("")
        assert result["intent"] == "chat"

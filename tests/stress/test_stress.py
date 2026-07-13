"""Stress Tests —— 验证 AI-Lab 在高负载下的稳定性。

简化版，覆盖核心路径。
"""

import asyncio
import time
import sys
sys.path.insert(0, ".")

import pytest
pytestmark = pytest.mark.asyncio(loop_scope="function")

from core.memory.models import MemoryType, MemoryItem
from core.memory.storage.sqlite_episodic import SQLiteEpisodicStore
from core.task.models import TaskRequest, TaskType, TaskPriority
from core.task.manager import TaskManager
from core.task.runtime import TaskRuntime
from core.agents.models import AgentRequest, AgentInfo
from core.agents.runtime import DefaultAgentRuntime
from core.agents.config import AgentConfig
from core.providers.llm.mock import MockLLMProvider
from core.tools.registry import ToolRegistry
from core.tools.builtin.echo import EchoTool
from core.tools.models import ToolRequest
from core.tools.executor import ToolExecutor


class TestStress:

    async def test_stress_episodic_1000_saves(self):
        """1000 episodic memory saves through SQLite store."""
        import tempfile, os
        tmp = tempfile.mkdtemp()
        db = os.path.join(tmp, "stress.db")
        store = SQLiteEpisodicStore(db_path=db)
        await store.initialize()
        ids = []
        t0 = time.time()
        for i in range(1000):
            item = MemoryItem(
                memory_type=MemoryType.EPISODIC,
                content={"text": f"stress-{i}"},
                metadata={"index": i},
            )
            await store.save(item)
            ids.append(item.id)
        elapsed = time.time() - t0
        assert len(ids) == 1000
        assert elapsed < 30
        await store.close()

    async def test_stress_tool_100_calls(self):
        """100 tool calls through ToolExecutor."""
        registry = ToolRegistry()
        echo = EchoTool()
        registry.register(echo.info, lambda: EchoTool())
        executor = ToolExecutor(registry=registry)
        t0 = time.time()
        for i in range(100):
            req = ToolRequest(tool_name="echo", arguments={"text": f"s{i}"})
            result = await executor.execute(req)
            assert result.success
        elapsed = time.time() - t0
        assert elapsed < 30

    async def test_stress_agent_50_requests(self):
        """50 agent requests."""
        llm = MockLLMProvider()
        await llm.initialize()
        info = AgentInfo(name="stress-agent")
        config = AgentConfig(memory_enabled=False, knowledge_enabled=False, tools_enabled=False)
        runtime = DefaultAgentRuntime(info=info, llm_provider=llm, config=config)
        await runtime.initialize()
        t0 = time.time()
        for i in range(50):
            req = AgentRequest(user_input=f"Stress {i}", session_id="s", agent_id=info.id)
            resp = await runtime.run(req)
            assert resp.answer is not None
        elapsed = time.time() - t0
        assert elapsed < 60
        await runtime.shutdown()
        await llm.shutdown()

    async def test_stress_task_200(self):
        """200 task creations."""
        mgr = TaskManager()
        runtime = TaskRuntime(manager=mgr)
        await runtime.initialize()
        t0 = time.time()
        ids = []
        for i in range(200):
            req = TaskRequest(task_name=f"t-{i}", task_type=TaskType.ONE_SHOT, priority=TaskPriority.LOW)
            info = await runtime.create_task(req)
            ids.append(info.id)
        elapsed = time.time() - t0
        assert len(ids) == 200
        assert elapsed < 30
        await runtime.shutdown()

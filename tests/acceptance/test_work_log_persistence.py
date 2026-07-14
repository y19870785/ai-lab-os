"""Work-log persistence across independent system lifecycles."""

from pathlib import Path

import pytest

from applications.models import ApplicationRequest
from core.memory.models import MemoryQuery, MemoryType
from core.system import create_system, make_test_settings

pytestmark = pytest.mark.asyncio(loop_scope="function")


async def test_work_log_survives_system_restart(tmp_path: Path):
    settings = make_test_settings(tmp_path)

    first = await create_system(settings)
    await first.start()
    response = await first.application_runtime.execute(ApplicationRequest(
        application_name="ceo-assistant",
        user_input="记录: SP-001 跨重启持久化验收",
    ))
    assert response.status == "ok"
    await first.shutdown()

    second = await create_system(settings)
    await second.start()
    try:
        items = await second.memory_manager.retrieve_memory(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=20)
        )
        assert any("SP-001" in item.content.get("raw_text", "") for item in items)
    finally:
        await second.shutdown()

"""API work-log acceptance through the lifespan-owned system."""

import asyncio

from fastapi.testclient import TestClient

from api.app import create_app
from core.memory.models import MemoryQuery, MemoryType
from core.system import make_test_settings


def test_post_work_log_writes_unified_episodic_memory(tmp_path):
    app = create_app(make_test_settings(tmp_path))
    with TestClient(app) as client:
        response = client.post(
            "/work-logs",
            json={"user_input": "今天完成 API 真实派发验收"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert "Echo" not in response.json()["answer"]

        system = app.state.system
        items = asyncio.run(system.memory_manager.retrieve_memory(
            MemoryQuery(memory_type=MemoryType.EPISODIC, top_k=10)
        ))
        assert any(item.content.get("type") == "work_log" for item in items)
        assert system.application_registry.get_instance_by_name("ceo-assistant") is system.ceo_assistant

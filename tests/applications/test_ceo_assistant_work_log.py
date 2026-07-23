"""CEO Assistant Work Log create/query boundary tests."""

from datetime import datetime, timezone

import pytest

from applications.ceo_assistant.intent import IntentEffect, decide_intent
from applications.models import ApplicationRequest
from core.system import create_system, make_test_settings
from core.workspace.models import WorkspaceKey
from tests.helpers.clock import MutableClock

NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


def test_work_log_intent_effects_are_narrow():
    assert decide_intent("记录：完成蜂蜡报价").effect == IntentEffect.WRITE
    assert decide_intent("查看今天的工作记录").effect == IntentEffect.READ
    assert decide_intent("查看标签为蜂蜡的工作记录").effect == IntentEffect.READ


@pytest.mark.asyncio
async def test_create_then_today_tag_status_and_id_queries_are_read_only(tmp_path):
    system = await create_system(
        make_test_settings(tmp_path, timezone_name="Asia/Shanghai"),
        clock=MutableClock(NOW),
    )
    await system.start()
    workspace = WorkspaceKey(workspace_id="alpha")
    try:
        created = await system.application_runtime.execute(
            ApplicationRequest(
                application_name="ceo-assistant",
                user_input="记录：今天和张经理确认了蜂蜡报价",
                workspace_key=workspace,
            )
        )
        identifier = created.metadata["id"]
        with system.database_manager.lease("episodic") as conn:
            before = conn.execute(
                "SELECT COUNT(*) FROM episodic_memories"
            ).fetchone()[0]

        for query in (
            "查看今天的工作记录",
            f"查看工作记录 {identifier}",
            "查看张经理相关的工作记录",
            "查看标签为蜂蜡的工作记录",
            "查看状态为已完成的工作记录",
            "查看 2026-07-20 到 2026-07-23 的工作记录",
        ):
            response = await system.application_runtime.execute(
                ApplicationRequest(
                    application_name="ceo-assistant",
                    user_input=query,
                    workspace_key=workspace,
                )
            )
            assert response.status == "ok"
            assert response.metadata["count"] >= 1

        with system.database_manager.lease("episodic") as conn:
            after = conn.execute(
                "SELECT COUNT(*) FROM episodic_memories"
            ).fetchone()[0]
        assert after == before
    finally:
        await system.shutdown()

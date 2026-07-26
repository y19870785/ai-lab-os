"""CEO Assistant delegates the historical brief intent to Daily Review."""

import inspect
from datetime import UTC, datetime

import pytest

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.intent import decide_intent
from applications.config import ApplicationConfig
from applications.models import ApplicationRequest
from core.errors import ErrorCategory, FailureException
from tests.core.daily_review.helpers import (
    WORKSPACE,
    FrozenCountingClock,
    make_service,
)
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION


class _Bomb:
    def __getattr__(self, name):
        raise AssertionError(f"legacy dependency was accessed: {name}")


def _assistant(instant: datetime):
    service = make_service(FrozenCountingClock(instant))
    assistant = CEOAssistant(
        memory_manager=_Bomb(),
        user_task_service=_Bomb(),
        work_log_service=_Bomb(),
        daily_agenda=_Bomb(),
        daily_review_service=service,
        config=ApplicationConfig(provider_mode="test"),
        admission=PERMISSIVE_TEST_ADMISSION,
    )
    return assistant, service


@pytest.mark.asyncio
async def test_brief_runtime_uses_only_daily_review_and_returns_metadata():
    assistant, _ = _assistant(datetime(2026, 7, 27, 12, tzinfo=UTC))

    response = await assistant.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input="今日简报",
        workspace_key=WORKSPACE,
    ))

    assert response.status == "ok"
    assert response.metadata["intent"] == "brief"
    assert response.metadata["effect"] == "read"
    assert response.metadata["daily_review_query"] == {
        "review_date": "today",
        "limit": 50,
        "offset": 0,
    }
    assert response.metadata["daily_review"]["workspace"] == {
        "tenant_id": WORKSPACE.tenant_id,
        "workspace_id": WORKSPACE.workspace_id,
        "namespace": WORKSPACE.namespace,
    }
    assert "[MOCK MODE]" not in response.answer


@pytest.mark.asyncio
async def test_yesterday_wording_builds_the_same_default_query_model():
    assistant, _ = _assistant(datetime(2026, 7, 27, 12, tzinfo=UTC))

    response = await assistant.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input="昨天做了哪些事",
        workspace_key=WORKSPACE,
    ))

    assert response.metadata["daily_review_query"] == {
        "review_date": "yesterday",
        "limit": 50,
        "offset": 0,
    }
    assert response.metadata["daily_review"]["review_date"] == "2026-07-26"


@pytest.mark.parametrize(
    "text",
    [
        "简报",
        "每日简报",
        "今日简报",
        "今日总结",
        "今天做了什么",
        "今天做了哪些事",
        "今天已经完成了什么",
        "查看今天的完成记录",
        "今天的工作",
        "今日概览",
        "daily brief",
        "工作概览",
        "昨日简报",
        "昨天简报",
        "昨日总结",
        "昨天总结",
        "昨天做了什么",
        "昨天做了哪些事",
        "昨天的工作",
    ],
)
def test_daily_review_phrases_are_deterministic_read_intents(text):
    decision = decide_intent(text)

    assert decision.intent == "brief"
    assert decision.effect.value == "read"


def test_handle_brief_has_no_legacy_aggregation_dependencies():
    source = inspect.getsource(CEOAssistant._handle_brief)

    for forbidden in (
        "datetime.now",
        "self._user_tasks",
        "self._work_logs",
        "self._memory",
        "self._daily_agenda",
        "priority_order",
        "建议优先处理",
    ):
        assert forbidden not in source
    assert "self._daily_review.get" in source


@pytest.mark.asyncio
async def test_missing_daily_review_is_not_configured():
    assistant = CEOAssistant(
        config=ApplicationConfig(provider_mode="test"),
        admission=PERMISSIVE_TEST_ADMISSION,
    )

    with pytest.raises(FailureException) as exc_info:
        await assistant._handle_brief(ApplicationRequest(
            application_name="ceo-assistant",
            user_input="今日简报",
            workspace_key=WORKSPACE,
        ))

    assert exc_info.value.failure.code == "daily_review.unavailable"
    assert exc_info.value.failure.category == ErrorCategory.NOT_CONFIGURED

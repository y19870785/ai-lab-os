"""CEO Assistant delegates the historical brief intent to Daily Review."""

import inspect
from datetime import UTC, datetime

import pytest

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.intent import (
    decide_intent,
    is_generic_daily_review_request,
    resolve_daily_review_date,
)
from applications.config import ApplicationConfig
from applications.models import ApplicationRequest
from core.errors import ErrorCategory, FailureException
from tests.core.daily_review.helpers import (
    WORKSPACE,
    FrozenCountingClock,
    empty_sources,
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
    ("text", "expected"),
    [
        ("简报", "today"),
        ("每日简报", "today"),
        ("请给我一份简报。", "today"),
        ("请给我简报", "today"),
        ("帮我看一下简报", "today"),
        ("看一下简报！", "today"),
        ("查看简报", "today"),
        ("给我来一份简报", "today"),
        ("做一份简报", "today"),
        ("生成一份简报", "today"),
        ("今日简报", "today"),
        ("今天简报", "today"),
        ("今日总结", "today"),
        ("今天做了什么", "today"),
        ("今天做了哪些事", "today"),
        ("今天已经完成了什么", "today"),
        ("查看今天的完成记录", "today"),
        ("今天的工作", "today"),
        ("今日概览", "today"),
        ("daily brief", "today"),
        ("工作概览", "today"),
        ("昨日简报", "yesterday"),
        ("昨天简报", "yesterday"),
        ("昨日总结", "yesterday"),
        ("昨天总结", "yesterday"),
        ("昨天做了什么", "yesterday"),
        ("昨天做了哪些事", "yesterday"),
        ("昨天的工作", "yesterday"),
    ],
)
def test_daily_review_phrases_are_deterministic_read_intents(text, expected):
    decision = decide_intent(text)

    assert decision.intent == "brief"
    assert decision.effect.value == "read"
    assert resolve_daily_review_date(text).value == expected


@pytest.mark.parametrize(
    "text",
    [
        "简报",
        "每日简报",
        "daily brief",
        "工作概览",
        "请给我一份简报",
        "请给我简报",
        "帮我看一下简报",
        "看一下简报",
        "查看简报",
        "给我来一份简报",
        "做一份简报",
        "生成一份简报",
        "  麻烦给我来一份简报，谢谢！  ",
        "please daily brief",
        "daily brief.",
        "查看简报，",
    ],
)
def test_generic_brief_positive_grammar_matches_complete_request(text):
    assert is_generic_daily_review_request(text)
    assert resolve_daily_review_date(text).value == "today"


@pytest.mark.parametrize(
    "text",
    [
        "2026年7月简报",
        "7月简报",
        "2026年简报",
        "2026年度简报",
        "7月份简报",
        "第三季度简报",
        "第四季度工作概览",
        "2026年第一季度简报",
        "上半年简报",
        "下半年简报",
        "年初简报",
        "年底简报",
        "春节后简报",
        "国庆前简报",
        "假期后简报",
    ],
)
def test_generic_brief_positive_grammar_rejects_temporal_qualifiers(text):
    assert not is_generic_daily_review_request(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("今天", "today"),
        ("今日", "today"),
        ("昨天", "yesterday"),
        ("昨日", "yesterday"),
    ],
)
def test_supported_date_selectors_resolve_without_generic_brief(text, expected):
    assert resolve_daily_review_date(text).value == expected


@pytest.mark.parametrize(
    "text",
    [
        "明日简报",
        "明天简报",
        "后天简报",
        "前天简报",
        "上周简报",
        "本周简报",
        "上个月简报",
        "2026-07-01 简报",
        "2026年7月1日简报",
        "7月1日简报",
        "周一简报",
        "星期五简报",
        "礼拜天简报",
        "两天前简报",
        "三天后简报",
        "过去三天简报",
        "最近七天简报",
        "本季度简报",
        "上季度简报",
        "2026/07/01 简报",
        "2026.07.01 简报",
        "7月1号简报",
        "1号简报",
        "周一到周五简报",
        "昨天到今天简报",
        "昨天和今天简报",
        "今日或昨日总结",
        "今天到明天简报",
        "2026年7月简报",
        "7月简报",
        "2026年简报",
        "2026年度简报",
        "7月份简报",
        "第三季度简报",
        "第四季度工作概览",
        "2026年第一季度简报",
        "上半年简报",
        "下半年简报",
        "年初简报",
        "年底简报",
        "春节后简报",
        "国庆前简报",
        "假期后简报",
    ],
)
def test_explicit_unsupported_dates_take_the_brief_validation_path(text):
    decision = decide_intent(text)

    assert decision.intent == "brief"
    assert decision.effect.value == "read"
    with pytest.raises(FailureException) as exc_info:
        resolve_daily_review_date(text, trace_id="trace-date-invalid")

    failure = exc_info.value.failure
    assert failure.code == "daily_review.date_invalid"
    assert failure.category == ErrorCategory.VALIDATION
    assert failure.component == "daily_review"
    assert failure.operation == "get"
    assert failure.trace_id == "trace-date-invalid"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "明日简报",
        "周一简报",
        "两天前简报",
        "2026/07/01 简报",
        "周一到周五简报",
        "昨天和今天简报",
        "2026年7月简报",
        "7月简报",
        "第三季度简报",
        "上半年简报",
        "春节后简报",
    ],
)
async def test_unsupported_date_fails_before_clock_or_source_reads(text):
    clock = FrozenCountingClock(datetime(2026, 7, 27, 12, tzinfo=UTC))
    sources = empty_sources()
    assistant = CEOAssistant(
        daily_review_service=make_service(clock, sources),
        config=ApplicationConfig(provider_mode="test"),
        admission=PERMISSIVE_TEST_ADMISSION,
    )

    with pytest.raises(FailureException) as exc_info:
        await assistant.run(ApplicationRequest(
            application_name="ceo-assistant",
            user_input=text,
            workspace_key=WORKSPACE,
        ))

    failure = exc_info.value.failure
    assert failure.code == "daily_review.date_invalid"
    assert failure.category == ErrorCategory.VALIDATION
    assert clock.calls == 0
    assert sources.work_logs.calls == []
    assert sources.waiting_for.calls == []
    assert sources.reminders.calls == []
    assert sources.inbox.calls == []
    assert sources.user_tasks.calls == []


@pytest.mark.parametrize(
    "text",
    [
        "简报",
        "每日简报",
        "daily brief",
        "请给我一份简报",
        "看一下简报",
        "请给我简报",
        "帮我看一下简报",
        "查看简报",
        "给我来一份简报",
        "做一份简报",
        "生成一份简报",
    ],
)
@pytest.mark.asyncio
async def test_legacy_generic_brief_phrases_remain_today(text):
    assistant, _ = _assistant(datetime(2026, 7, 27, 12, tzinfo=UTC))

    response = await assistant.run(ApplicationRequest(
        application_name="ceo-assistant",
        user_input=text,
        workspace_key=WORKSPACE,
    ))

    assert response.metadata["daily_review_query"]["review_date"] == "today"


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

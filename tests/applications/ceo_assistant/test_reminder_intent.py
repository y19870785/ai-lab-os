from datetime import datetime, timezone

import pytest

from applications.ceo_assistant.reminder_intent import TaskReminderIntentParser
from core.errors import FailureException
from tests.helpers.clock import MutableClock


@pytest.fixture
def parser():
    clock = MutableClock(datetime(2026, 7, 16, 6, 0, tzinfo=timezone.utc))
    return TaskReminderIntentParser("Asia/Shanghai", clock)


@pytest.mark.parametrize(("phrase", "expected"), [
    ("今天 15:00 提醒我联系张经理", "2026-07-16T07:00:00+00:00"),
    ("明天 15：00 提醒我联系张经理", "2026-07-17T07:00:00+00:00"),
    ("今天下午3点提醒我联系张经理", "2026-07-16T07:00:00+00:00"),
    ("明天晚上8点提醒我整理报价", "2026-07-17T12:00:00+00:00"),
    ("明天下午3点半提醒我联系张经理", "2026-07-17T07:30:00+00:00"),
    ("明天下午3点一刻提醒我联系张经理", "2026-07-17T07:15:00+00:00"),
    ("明天下午3点45分提醒我联系张经理", "2026-07-17T07:45:00+00:00"),
])
def test_supported_reminder_phrases(parser, phrase, expected):
    parsed = parser.parse(phrase)
    assert parsed.kind == "reminder"
    assert parsed.title
    assert parsed.due_at.isoformat() == expected
    assert parsed.timezone == "Asia/Shanghai"


def test_task_without_time_has_no_due_at(parser):
    parsed = parser.parse("添加任务：联系张经理")
    assert parsed.kind == "task"
    assert parsed.title == "联系张经理"
    assert parsed.due_at is None
    assert parsed.time_unparsed is False


def test_task_with_supported_time_persists_due_at(parser):
    parsed = parser.parse("添加任务：明天下午3点联系张经理")
    assert parsed.kind == "task"
    assert parsed.title == "联系张经理"
    assert parsed.due_at.isoformat() == "2026-07-17T07:00:00+00:00"
    assert parsed.time_unparsed is False


def test_unsupported_task_time_is_explicitly_degraded(parser):
    parsed = parser.parse("添加任务：下周联系张经理")
    assert parsed.kind == "task"
    assert parsed.due_at is None
    assert parsed.time_unparsed is True


@pytest.mark.parametrize("phrase", [
    "下周提醒我联系张经理",
    "提醒我联系张经理",
    "明天下午提醒我联系张经理",
    "明天下午3点三刻提醒我联系张经理",
    "明天下午3点45分30秒提醒我联系张经理",
])
def test_unsupported_reminder_time_fails(parser, phrase):
    with pytest.raises(FailureException) as exc_info:
        parser.parse(phrase)
    assert exc_info.value.failure.code == "reminder.time_unsupported"


def test_past_time_fails_explicitly(parser):
    with pytest.raises(FailureException) as exc_info:
        parser.parse("今天上午9点提醒我联系张经理")
    assert exc_info.value.failure.code == "reminder.time_in_past"

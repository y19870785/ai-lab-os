from datetime import datetime, timezone

import pytest

from applications.ceo_assistant.application import CEOAssistant
from applications.ceo_assistant.reminder_errors import ReminderUserErrorPresenter
from applications.ceo_assistant.reminder_intent import TaskReminderIntentParser
from applications.models import ApplicationRequest
from core.errors import ErrorCategory, FailureException, FailureInfo
from tests.helpers.admission import PERMISSIVE_TEST_ADMISSION
from tests.helpers.clock import MutableClock


def _app() -> CEOAssistant:
    clock = MutableClock(datetime(2026, 7, 17, 2, 0, tzinfo=timezone.utc))
    return CEOAssistant(
        user_task_service=object(),
        task_intent_parser=TaskReminderIntentParser("Asia/Shanghai", clock),
        admission=PERMISSIVE_TEST_ADMISSION,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("text", "code", "guidance"),
    [
        ("查看提醒", "reminder.target_required", "请提供要查看的提醒标题或 Reminder ID"),
        ("取消提醒", "reminder.target_required", "请提供要取消的提醒标题或 Reminder ID"),
        ("把提醒改到明天下午4点", "reminder.target_required", "请提供要改期的提醒标题或 Reminder ID"),
        ("把提醒 rem_example 改期", "reminder.time_required", "请提供新的提醒时间"),
        ("30分钟后提醒我测试", "reminder.time_unsupported", "今天下午3点"),
        ("把提醒 rem_example 改到30分钟后", "reminder.time_unsupported", "明天上午9点"),
        ("今天上午9点提醒我测试", "reminder.time_in_past", "提醒时间已经过去"),
    ],
)
async def test_reminder_failures_are_stable_actionable_and_chinese(text, code, guidance):
    with pytest.raises(FailureException) as exc_info:
        await _app().run(ApplicationRequest(application_name="ceo-assistant", user_input=text))

    failure = exc_info.value.failure
    assert failure.code == code
    assert failure.category == ErrorCategory.VALIDATION
    assert guidance in failure.message
    assert "MOCK MODE" not in failure.message
    assert "API_KEY" not in failure.message


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("reminder.not_found", "没有找到匹配的提醒"),
        ("reminder.ambiguous", "找到多条同名提醒"),
    ],
)
def test_presenter_localizes_management_failures_without_changing_codes(code, expected):
    failure = FailureInfo(
        code=code,
        category=ErrorCategory.NOT_FOUND,
        message="internal English message",
        component="reminder.management",
        operation="resolve",
    )
    presented = ReminderUserErrorPresenter.present(failure)
    assert presented.code == code
    assert expected in presented.message

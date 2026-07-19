"""Deterministic task/reminder intent parsing for the supported product slice."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Literal
from zoneinfo import ZoneInfo

from core.clock import Clock
from core.errors import ErrorCategory, FailureException, FailureInfo


_REMINDER_MARKERS = ("提醒我", "记得", "别忘了")
_TASK_PREFIX = re.compile(r"^(?:添加|创建)?(?:任务|待办)\s*[:：]?\s*")
_CHINESE_HOURS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
}
_TIME_EXPRESSION = re.compile(
    r"(?P<day>今天|明天)\s*"
    r"(?:(?P<period>上午|下午|晚上)\s*)?"
    r"(?P<hour>\d{1,2}|十一|十二|十|一|二|三|四|五|六|七|八|九)"
    r"(?:\s*[:：]\s*(?P<colon_minute>\d{1,2})|\s*点(?:(?P<half>半)|(?P<quarter>一刻)|(?P<point_minute>\d{1,2})分?)?)"
)


def _parse_hour(value: str) -> int:
    if value in _CHINESE_HOURS:
        return _CHINESE_HOURS[value]
    return int(value)


@dataclass(frozen=True)
class ParsedTaskIntent:
    kind: Literal["task", "reminder"]
    title: str
    due_at: datetime | None
    timezone: str
    time_unparsed: bool = False


class TaskReminderIntentParser:
    def __init__(self, timezone_name: str, clock: Clock) -> None:
        self._timezone_name = timezone_name
        self._zone = ZoneInfo(timezone_name)
        self._clock = clock

    def parse(self, text: str) -> ParsedTaskIntent:
        raw = text.strip()
        is_reminder = any(marker in raw for marker in _REMINDER_MARKERS)
        match = _TIME_EXPRESSION.search(raw)
        if match is None or self._has_unsupported_time_suffix(raw, match.end()):
            if is_reminder:
                self._fail("reminder.time_unsupported", "Reminder time is not supported")
            title = _TASK_PREFIX.sub("", raw).strip(" ，。:：")
            return ParsedTaskIntent(
                "task", title, None, self._timezone_name,
                time_unparsed=self._contains_time_hint(raw),
            )

        hour_token = match.group("hour")
        hour = _parse_hour(hour_token)
        minute = int(
            match.group("colon_minute")
            or match.group("point_minute")
            or (30 if match.group("half") else 15 if match.group("quarter") else 0)
        )
        period = match.group("period")
        if (
            minute > 59
            or (hour_token in _CHINESE_HOURS and period is None)
            or (period and not 1 <= hour <= 12)
            or (not period and hour > 23)
        ):
            if is_reminder:
                self._fail("reminder.time_unsupported", "Reminder time is not supported")
            title = _TASK_PREFIX.sub("", raw).strip(" ，。:：")
            return ParsedTaskIntent(
                "task", title, None, self._timezone_name, time_unparsed=True
            )
        if period in {"下午", "晚上"} and hour < 12:
            hour += 12
        elif period == "上午" and hour == 12:
            hour = 0

        local_now = self._clock.now().astimezone(self._zone)
        day = local_now.date() + timedelta(days=match.group("day") == "明天")
        local_due = datetime.combine(day, time(hour, minute), tzinfo=self._zone)
        due_at = local_due.astimezone(timezone.utc)
        if is_reminder and due_at <= self._clock.now().astimezone(timezone.utc):
            self._fail("reminder.time_in_past", "Reminder time must be in the future")

        title = raw[:match.start()] + raw[match.end():]
        for marker in _REMINDER_MARKERS:
            title = title.replace(marker, "")
        title = _TASK_PREFIX.sub("", title).strip(" ，。:：")
        if not title:
            self._fail(
                "reminder.title_missing" if is_reminder else "user_tasks.title_missing",
                "Reminder title is required" if is_reminder else "Task title is required",
            )
        return ParsedTaskIntent(
            "reminder" if is_reminder else "task",
            title,
            due_at,
            self._timezone_name,
        )

    @staticmethod
    def _has_unsupported_time_suffix(text: str, end: int) -> bool:
        return re.match(
            r"\s*(?:[二三四]刻|[零〇一二两三四五六七八九十]+(?:分|秒)|"
            r"\d{1,2}(?:分|秒)|刻|分|秒|左右)",
            text[end:],
        ) is not None

    @staticmethod
    def _contains_time_hint(text: str) -> bool:
        return re.search(
            r"今天|明天|后天|下周|周[一二三四五六日天]|月底|过几天|有空|早上|上午|下午|晚上|\d{1,2}\s*(?:[:：点])",
            text,
        ) is not None

    @staticmethod
    def _fail(code: str, message: str) -> None:
        raise FailureException(FailureInfo(
            code=code,
            category=ErrorCategory.VALIDATION,
            message=message,
            component="reminder.intent",
            operation="parse_time",
            retryable=False,
        ))

"""Trigger 引擎 —— 判断 Trigger 是否应该触发。

支持 Cron / Interval / One-shot / Manual / Event 五种触发类型。
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from core.scheduler.models import Trigger, TriggerType


class TriggerEngine:
    """Trigger 引擎 —— 纯函数，无副作用"""

    @staticmethod
    def should_fire(trigger: Trigger, now: datetime | None = None) -> bool:
        """判断 Trigger 是否应该触发"""
        now = now or datetime.now(UTC)
        if trigger.next_run_at is None:
            return False
        return now >= trigger.next_run_at

    @staticmethod
    def compute_next(trigger: Trigger, now: datetime | None = None) -> datetime | None:
        """计算下次触发时间"""
        now = now or datetime.now(UTC)

        if trigger.trigger_type == TriggerType.ONE_SHOT:
            return trigger.run_at
        elif trigger.trigger_type == TriggerType.INTERVAL:
            if trigger.interval_seconds <= 0:
                return None
            return now + timedelta(seconds=trigger.interval_seconds)
        elif trigger.trigger_type == TriggerType.CRON:
            return TriggerEngine._next_cron(trigger.cron_expression, now)
        elif trigger.trigger_type == TriggerType.MANUAL:
            return None  # 手动触发不自动计算
        elif trigger.trigger_type == TriggerType.EVENT:
            return None  # 事件触发由 EventBus 驱动
        return None

    @staticmethod
    def _cron_steps(expression: str) -> tuple[int, int] | None:
        """Parse only the documented UTC minute/hour step subset."""
        parts = expression.split()
        if len(parts) != 5 or parts[2:] != ["*", "*", "*"]:
            return None
        steps = []
        for field, maximum in zip(parts[:2], (60, 24), strict=True):
            if field == "*":
                steps.append(1)
                continue
            match = re.fullmatch(r"\*/([1-9][0-9]?)", field)
            if match is None or int(match[1]) > maximum:
                return None
            steps.append(int(match[1]))
        return steps[0], steps[1]

    @staticmethod
    def _next_cron(expression: str, now: datetime) -> datetime | None:
        """Return the earliest strictly future match in the bounded UTC subset."""
        steps = TriggerEngine._cron_steps(expression)
        if steps is None or now.tzinfo is None or now.utcoffset() is None:
            return None
        minute_step, hour_step = steps
        now = now.astimezone(UTC)
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        try:
            # Every supported expression matches midnight, so two days suffice.
            for day in (0, 1):
                date = midnight + timedelta(days=day)
                for hour in range(0, 24, hour_step):
                    if day == 0 and hour < now.hour:
                        continue
                    for minute in range(0, 60, minute_step):
                        candidate = date.replace(hour=hour, minute=minute)
                        if candidate > now:
                            return candidate
        except OverflowError:
            return None
        return None

    @staticmethod
    def validate(trigger: Trigger) -> bool:
        """验证 Trigger 配置是否合法"""
        if trigger.trigger_type == TriggerType.CRON:
            return TriggerEngine._cron_steps(trigger.cron_expression) is not None
        elif trigger.trigger_type == TriggerType.INTERVAL:
            return trigger.interval_seconds > 0
        elif trigger.trigger_type == TriggerType.ONE_SHOT:
            return trigger.run_at is not None
        elif trigger.trigger_type in (TriggerType.MANUAL, TriggerType.EVENT):
            return True
        return False

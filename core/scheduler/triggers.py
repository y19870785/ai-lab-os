"""Trigger 引擎 —— 判断 Trigger 是否应该触发。

支持 Cron / Interval / One-shot / Manual / Event 五种触发类型。
"""

from __future__ import annotations
from datetime import datetime, timezone, timedelta
from core.scheduler.models import Trigger, TriggerType


class TriggerEngine:
    """Trigger 引擎 —— 纯函数，无副作用"""

    @staticmethod
    def should_fire(trigger: Trigger, now: datetime | None = None) -> bool:
        """判断 Trigger 是否应该触发"""
        now = now or datetime.now(timezone.utc)
        if trigger.next_run_at is None:
            return False
        return now >= trigger.next_run_at

    @staticmethod
    def compute_next(trigger: Trigger, now: datetime | None = None) -> datetime | None:
        """计算下次触发时间"""
        now = now or datetime.now(timezone.utc)

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
    def _next_cron(expression: str, now: datetime) -> datetime | None:
        """简易 Cron 解析 —— 支持 5 字段格式: minute hour day month weekday"""
        if not expression or expression.count(" ") != 4:
            return None

        try:
            parts = expression.strip().split()
            minute, hour, day, month, weekday = parts

            # 简易实现：仅支持 "*/N" 和 "*" 格式
            next_dt = now + timedelta(minutes=1)
            next_dt = next_dt.replace(second=0, microsecond=0)

            if minute.startswith("*/"):
                interval = int(minute[2:])
                current_minute = next_dt.minute
                minutes_to_add = interval - (current_minute % interval)
                if minutes_to_add == 0:
                    minutes_to_add = interval
                next_dt += timedelta(minutes=minutes_to_add)

            if hour.startswith("*/"):
                interval = int(hour[2:])
                current_hour = next_dt.hour
                hours_to_add = interval - (current_hour % interval)
                if hours_to_add == 0:
                    hours_to_add = interval
                next_dt += timedelta(hours=hours_to_add)

            return next_dt
        except (ValueError, IndexError):
            return None

    @staticmethod
    def validate(trigger: Trigger) -> bool:
        """验证 Trigger 配置是否合法"""
        if trigger.trigger_type == TriggerType.CRON:
            return bool(trigger.cron_expression and trigger.cron_expression.count(" ") == 4)
        elif trigger.trigger_type == TriggerType.INTERVAL:
            return trigger.interval_seconds > 0
        elif trigger.trigger_type == TriggerType.ONE_SHOT:
            return trigger.run_at is not None
        elif trigger.trigger_type in (TriggerType.MANUAL, TriggerType.EVENT):
            return True
        return False

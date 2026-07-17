"""Chinese, actionable presentation for stable Reminder failure codes."""

from __future__ import annotations

from core.errors import ErrorCategory, FailureInfo


class ReminderUserErrorPresenter:
    """Keep machine codes stable while making user-facing failures actionable."""

    _MESSAGES = {
        "reminder.time_unsupported": (
            "目前暂不支持这类时间表达。请使用明确时间，例如："
            "今天下午3点、明天上午9点或明天 15:00。"
        ),
        "reminder.time_in_past": "提醒时间已经过去，请提供一个未来时间。",
        "reminder.not_found": "没有找到匹配的提醒，请检查标题或 Reminder ID。",
        "reminder.ambiguous": "找到多条同名提醒，请使用具体的 Reminder ID。",
    }

    @classmethod
    def present(cls, failure: FailureInfo) -> FailureInfo:
        message = cls._MESSAGES.get(failure.code)
        return failure if message is None else failure.model_copy(update={"message": message})

    @staticmethod
    def target_required(*, action: str, trace_id: str) -> FailureInfo:
        examples = {
            "查看": "查看提醒 rem_xxx，或查看“联系张经理”的提醒，也可以说查看我的提醒。",
            "取消": "取消提醒 rem_xxx，或取消“联系张经理”的提醒。",
            "改期": "把提醒 rem_xxx 改到明天下午4点。",
        }
        operations = {"查看": "view", "取消": "cancel", "改期": "reschedule"}
        return FailureInfo(
            code="reminder.target_required",
            category=ErrorCategory.VALIDATION,
            message=f"请提供要{action}的提醒标题或 Reminder ID。例如：{examples[action]}",
            component="reminder.management",
            operation=f"{operations[action]}_natural_language",
            retryable=False,
            trace_id=trace_id,
        )

    @staticmethod
    def time_required(*, trace_id: str) -> FailureInfo:
        return FailureInfo(
            code="reminder.time_required",
            category=ErrorCategory.VALIDATION,
            message="请提供新的提醒时间。例如：把提醒 rem_xxx 改到明天下午4点。",
            component="reminder.management",
            operation="reschedule_natural_language",
            retryable=False,
            trace_id=trace_id,
        )

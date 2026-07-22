"""Deterministic Chinese presentation for Waiting-For failure codes."""

from __future__ import annotations

from core.errors import FailureInfo


class WaitingForUserErrorPresenter:
    """Change only user-facing messages; machine failure semantics stay immutable."""

    _MESSAGES = {
        "inbox.waiting_for.fields_missing": (
            "确认等待事项需要 Inbox ID、subject、waiting_on，以及 expected_by "
            "或 next_review_at。请按返回的确认命令模板补全。"
        ),
        "inbox.waiting_for.timezone_invalid": "timezone 无效，请使用有效的 IANA 时区，例如 Asia/Shanghai。",
        "inbox.waiting_for.unavailable": "Waiting-For 服务当前不可用，未写入任何对象。",
        "inbox.waiting_for.source_mismatch": "确定性 Waiting-For ID 已被其他来源占用，未覆盖现有对象。",
        "waiting_for.time_unsupported": (
            "暂不支持该时间表达。请使用今天或明天的明确时间，"
            "例如“明天下午三点”，或带 offset 的 ISO-8601 时间。"
        ),
        "waiting_for.get.not_found": "没有找到该 Waiting-For，请检查 canonical wf_ ID。",
        "waiting_for.events.not_found": "没有找到该 Waiting-For 的历史，请检查 canonical wf_ ID。",
        "waiting_for.follow_up.conflict": "当前状态或 revision 不允许催办；未自动重试。",
        "waiting_for.snooze.conflict": "当前状态或 revision 不允许延期；未自动重试。",
        "waiting_for.resolve.conflict": "解决操作发生状态或 revision 冲突；未自动重试。",
        "waiting_for.cancel.conflict": "取消操作发生状态或 revision 冲突；未自动重试。",
        "waiting_for.reopen.conflict": "重新打开操作发生状态或 revision 冲突；未自动重试。",
    }

    @classmethod
    def present(cls, failure: FailureInfo) -> FailureInfo:
        message = cls._MESSAGES.get(failure.code)
        return failure if message is None else failure.model_copy(update={"message": message})

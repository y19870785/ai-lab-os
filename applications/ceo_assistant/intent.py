"""Deterministic intent decisions with explicit side-effect classification."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class IntentEffect(str, Enum):
    READ = "read"
    WRITE = "write"
    CHAT = "chat"


@dataclass(frozen=True)
class IntentDecision:
    intent: str
    confidence: float
    effect: IntentEffect


_TODAY_REMINDER_QUERIES = {
    "今天都有什么事",
    "今天有什么事",
    "今天都有哪些提醒",
    "今天有什么提醒",
    "今天的提醒",
    "查看今天的提醒",
}
_PENDING_REMINDER_QUERIES = {
    "我今天有什么要做的",
    "接下来有什么提醒",
    "还有什么提醒",
    "待处理提醒有哪些",
    "查看待触发提醒",
}
_ALL_REMINDER_QUERIES = {
    "查看我的提醒",
    "查看全部提醒",
    "有哪些提醒",
}
_WORK_LOG_PREFIXES = (
    "记录:", "记录：", "记录 ", "记录一下", "记一条工作记录",
    "写一条工作记录", "工作日志", "log:", "log ",
)
_WORK_LOG_ACTIONS = (
    "完成了", "处理了", "确认了", "联系了", "收到了", "见了",
    "开了会", "参加了会议",
)


def _normalized_query(text: str) -> str:
    return re.sub(r"[\s?？!！。]+$", "", text.strip().lower())


def _is_reminder_list_query(text: str) -> bool:
    normalized = _normalized_query(text)
    if normalized in (
        _TODAY_REMINDER_QUERIES
        | _PENDING_REMINDER_QUERIES
        | _ALL_REMINDER_QUERIES
    ):
        return True
    if "提醒" not in normalized:
        return False
    return any(marker in normalized for marker in (
        "查看今天", "查看我的", "查看全部", "待触发", "待处理",
        "接下来", "还有什么", "有哪些", "有什么提醒", "已触发", "失败提醒",
    ))


def _is_explicit_work_log(text: str) -> bool:
    normalized = text.lower().strip()
    if normalized.startswith(_WORK_LOG_PREFIXES):
        return True
    if normalized.endswith(("?", "？")) and any(
        marker in normalized for marker in ("什么", "哪些", "怎么", "如何", "是否", "有没有", "什么时候", "吗")
    ):
        return False
    return any(marker in normalized for marker in _WORK_LOG_ACTIONS)


_INBOX_LIST_QUERIES = {
    "看看我的收件箱",
    "还有哪些没整理",
    "列出待处理记录",
}
_INBOX_CAPTURE_PREFIXES = (
    "记一下",
    "先记下来",
    "把这个放到收件箱",
    "这个想法先存着",
)


def extract_inbox_capture_content(text: str) -> str | None:
    """Return captured text only for explicit, deterministic Inbox wording."""

    stripped = text.strip()
    for prefix in _INBOX_CAPTURE_PREFIXES:
        if stripped.startswith(prefix):
            content = stripped[len(prefix):].lstrip("，,:：。 ")
            return content or None
    return None


def decide_intent(user_input: str) -> IntentDecision:
    """Classify intent deterministically, preferring reads when wording is ambiguous."""

    text = user_input.lower().strip()

    if "提醒" in text and text.startswith("取消"):
        return IntentDecision("reminder_cancel", 1.0, IntentEffect.WRITE)
    if any(marker in text for marker in ("提醒我", "记得", "别忘了")):
        return IntentDecision("task", 1.0, IntentEffect.WRITE)
    if "提醒" in text and any(marker in text for marker in ("改到", "延后到", "改期")):
        return IntentDecision("reminder_reschedule", 1.0, IntentEffect.WRITE)

    if _is_reminder_list_query(text):
        return IntentDecision("reminder_list", 1.0, IntentEffect.READ)

    daily_agenda_markers = (
        "今天有什么安排", "今天的日程", "查看今天安排", "查看今日日程",
        "接下来三个小时有什么安排", "未来三小时有什么要做的",
        "未来三小时有什么", "接下来有什么事",
        "有哪些需要注意的事项", "有哪些失败的提醒", "有没有逾期任务",
        "今天已经完成了什么", "今天做了哪些事", "查看今天的完成记录",
    )
    if any(marker in text for marker in daily_agenda_markers):
        return IntentDecision("daily_agenda", 1.0, IntentEffect.READ)
    if _normalized_query(text) in _INBOX_LIST_QUERIES:
        return IntentDecision("inbox_list", 1.0, IntentEffect.READ)
    if text.startswith(("查看提醒", "查看这条提醒")):
        return IntentDecision("reminder_detail", 1.0, IntentEffect.READ)

    if text.startswith(_WORK_LOG_PREFIXES):
        return IntentDecision("work_log", 1.0, IntentEffect.WRITE)
    if extract_inbox_capture_content(text) is not None:
        return IntentDecision("inbox_capture", 1.0, IntentEffect.WRITE)

    brief_keywords = (
        "简报", "今日总结", "今天做了什么", "今天的工作", "今日概览",
        "daily brief", "工作概览",
    )
    if any(keyword in text for keyword in brief_keywords):
        return IntentDecision("brief", 0.9, IntentEffect.READ)

    decision_keywords = ("决定", "决策", "选择", "采用", "确认使用", "不先做", "放弃")
    if any(keyword in text for keyword in decision_keywords):
        return IntentDecision("decision", 0.7, IntentEffect.WRITE)

    task_keywords = ("任务", "待办", "todo", "task", "截止", "完成任务", "取消任务", "暂停")
    if any(keyword in text for keyword in task_keywords):
        effect = IntentEffect.READ if any(
            marker in text for marker in ("查看", "有什么", "列表", "查询", "当前任务", "待办列表")
        ) else IntentEffect.WRITE
        return IntentDecision("task", 0.8, effect)

    knowledge_keywords = ("什么是", "解释", "法规", "标准", "规定", "文档", "查询", "查找", "怎么")
    if any(keyword in text for keyword in knowledge_keywords):
        return IntentDecision("knowledge", 0.7, IntentEffect.READ)

    if _is_explicit_work_log(text):
        return IntentDecision("work_log", 0.9, IntentEffect.WRITE)

    return IntentDecision("chat", 0.5, IntentEffect.CHAT)

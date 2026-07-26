"""Pure natural-language presentation for structured Daily Review results."""

from __future__ import annotations

from core.daily_review.models import DailyReview, DailyReviewSourceStatus

_SECTION_LABELS = (
    ("blocked", "阻塞"),
    ("follow_ups", "待跟进"),
    ("in_progress", "进行中"),
    ("completed", "已完成"),
    ("informational", "信息"),
    ("pending_inbox", "待整理 Inbox"),
)


def present_daily_review(review: DailyReview) -> str:
    """Format the current page without adding, removing, or reordering facts."""

    page = review.page
    lines = [
        f"每日复盘 — {review.review_date.isoformat()} ({review.timezone})",
        (
            f"事实窗口：[{review.period_start.isoformat()}, "
            f"{review.period_end.isoformat()})"
        ),
        f"截至：{review.as_of.isoformat()}",
        (
            f"分页：{page.count}/{page.total_count}，"
            f"limit={page.limit}，offset={page.offset}，"
            f"has_more={str(page.has_more).lower()}"
        ),
    ]

    gaps = [
        f"{source.value}={status.value}"
        for source, status in review.source_status.items()
        if status != DailyReviewSourceStatus.AVAILABLE
    ]
    if gaps:
        lines.append("来源缺口：" + "，".join(gaps))

    for field_name, label in _SECTION_LABELS:
        section = getattr(review, field_name)
        lines.append(
            f"{label}（本页 {section.page_item_count} / "
            f"总计 {section.section_total_count}）"
        )
        for item in section.items:
            effective = (
                item.effective_at.isoformat()
                if item.effective_at is not None
                else "无时间"
            )
            lines.append(
                f"- {item.title} [{item.source_id}] "
                f"{item.reason_code} @ {effective}"
            )

    return "\n".join(lines)

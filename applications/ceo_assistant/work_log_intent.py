"""Deterministic Work Log query parsing for the CEO Assistant."""

from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from core.work_log import WorkLogQuery, WorkLogStatus

_ID = re.compile(r"(wl_[0-9a-f]{32}|wl_legacy_[0-9a-f]{64}|inbox_wl_[0-9a-f]{24})")
_RANGE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*到\s*(\d{4}-\d{2}-\d{2})")


def is_work_log_query(text: str) -> bool:
    normalized = text.strip().lower()
    if not any(marker in normalized for marker in ("工作记录", "工作日志")):
        return False
    return any(
        marker in normalized
        for marker in ("查看", "查询", "哪些", "列表", "相关", "标签", "状态")
    )


def parse_work_log_query(
    text: str, *, now: datetime, timezone_name: str
) -> tuple[str | None, WorkLogQuery]:
    """Return an exact id or a deterministic list query."""

    identifier = _ID.search(text)
    if identifier:
        return identifier.group(1), WorkLogQuery()

    zone = ZoneInfo(timezone_name)
    date_from = date_to = None
    if "今天" in text:
        local = now.astimezone(zone).date()
        date_from = datetime.combine(local, time.min, tzinfo=zone).astimezone(
            timezone.utc
        )
        date_to = date_from + timedelta(days=1)
    else:
        date_range = _RANGE.search(text)
        if date_range:
            start = datetime.fromisoformat(date_range.group(1)).date()
            end = datetime.fromisoformat(date_range.group(2)).date()
            date_from = datetime.combine(start, time.min, tzinfo=zone).astimezone(
                timezone.utc
            )
            date_to = datetime.combine(
                end + timedelta(days=1), time.min, tzinfo=zone
            ).astimezone(timezone.utc)

    target = None
    target_match = re.search(r"查看(.{1,80}?)相关的工作记录", text)
    if target_match:
        target = target_match.group(1).strip()

    tags: tuple[str, ...] = ()
    tag_match = re.search(r"标签为(.{1,64}?)的工作记录", text)
    if tag_match:
        tags = (tag_match.group(1).strip(),)

    status = None
    status_match = re.search(r"状态为(.{1,32}?)的工作记录", text)
    if status_match:
        raw_status = status_match.group(1).strip().casefold()
        status = {
            "已完成": WorkLogStatus.COMPLETED,
            "完成": WorkLogStatus.COMPLETED,
            "completed": WorkLogStatus.COMPLETED,
            "进行中": WorkLogStatus.IN_PROGRESS,
            "in_progress": WorkLogStatus.IN_PROGRESS,
            "阻塞": WorkLogStatus.BLOCKED,
            "blocked": WorkLogStatus.BLOCKED,
            "信息": WorkLogStatus.INFORMATIONAL,
            "informational": WorkLogStatus.INFORMATIONAL,
        }.get(raw_status)

    return None, WorkLogQuery(
        date_from=date_from,
        date_to=date_to,
        target=target,
        tags=tags,
        status=status,
        limit=50,
    )

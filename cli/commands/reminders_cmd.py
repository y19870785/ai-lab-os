"""List persisted Reminder inbox entries."""

from __future__ import annotations

import argparse
import json

from cli.runtime import query_reminder_inbox
from core.reminders import ReminderInboxStatus, ReminderInboxTimeScope


async def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m cli reminders")
    parser.add_argument("--status", choices=[item.value for item in ReminderInboxStatus])
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--today", action="store_true")
    scope.add_argument("--upcoming", action="store_true")
    parser.add_argument("--limit", type=int, default=20, choices=range(1, 101))
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--json", action="store_true", dest="as_json")
    options = parser.parse_args(args)
    if options.offset < 0:
        parser.error("--offset must be zero or greater")

    status = ReminderInboxStatus(options.status) if options.status else None
    time_scope = (
        ReminderInboxTimeScope.TODAY if options.today
        else ReminderInboxTimeScope.UPCOMING if options.upcoming
        else None
    )
    page = await query_reminder_inbox(
        statuses={status} if status else None,
        time_scope=time_scope,
        limit=options.limit,
        offset=options.offset,
    )
    if options.as_json:
        print(json.dumps(page.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return

    if not page.items:
        print("没有符合条件的提醒。")
        return
    print(f"{'STATUS':<12} {'TIME':<25} TITLE")
    for item in page.items:
        print(f"{item.status.value:<12} {item.scheduled_for.isoformat():<25} {item.task_title}")
        print(f"  Reminder ID: {item.reminder_id}")
    print(f"显示 {page.count} 条，offset={page.offset}，has_more={page.has_more}")

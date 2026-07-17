"""Daily agenda read-only CLI."""

from __future__ import annotations

import argparse
import json
import sys


async def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli agenda")
    view_group = parser.add_mutually_exclusive_group()
    view_group.add_argument("--today", action="store_true", help="Show today's agenda")
    view_group.add_argument("--next", type=int, metavar="HOURS", help="Next N hours")
    view_group.add_argument("--attention", action="store_true", help="Items needing attention")
    view_group.add_argument("--completed", action="store_true", help="Completed items")
    view_group.add_argument("--all", action="store_true", help="All items")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--limit", type=int, default=50, help="Items per page")
    parser.add_argument("--offset", type=int, default=0, help="Page offset")
    options = parser.parse_args(args)

    from cli.runtime import query_daily_agenda

    view = "today"
    window_hours = None
    if options.today:
        view = "today"
    elif options.next is not None:
        view = "next"
        window_hours = options.next
    elif options.attention:
        view = "attention"
    elif options.completed:
        view = "completed"
    elif options.all:
        view = "all"

    page = await query_daily_agenda(
        view=view, window_hours=window_hours, limit=options.limit, offset=options.offset,
    )

    if options.json:
        print(json.dumps(page.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    if not page.items:
        print("当前没有符合条件的日程安排。")
        return 0

    print(f'{"TIME":<20} {"SOURCE":<10} {"STATUS":<12} TITLE')
    print("-" * 70)
    for item in page.items:
        time_str = ""
        if item.scheduled_for:
            t = item.scheduled_for
            time_str = f"{t.hour:02d}:{t.minute:02d}"
        elif item.due_at:
            t = item.due_at
            time_str = f"due {t.hour:02d}:{t.minute:02d}"
        elif item.occurred_at:
            t = item.occurred_at
            time_str = f"{t.hour:02d}:{t.minute:02d}"
        else:
            time_str = "        "
        source = item.source.value[:10]
        status = item.status[:12]
        print(f"{time_str:<20} {source:<10} {status:<12} {item.title}")

    print()
    print(f"显示 {page.count} 条，view={view}，offset={page.offset}，has_more={page.has_more}")
    return 0

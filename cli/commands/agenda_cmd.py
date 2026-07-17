"""Daily agenda read-only CLI."""

from __future__ import annotations

import argparse
import json
import sys


async def agenda(args: argparse.Namespace, system) -> int:
    service = system.daily_agenda
    if service is None:
        print("Daily agenda is unavailable", file=sys.stderr)
        return 1

    view = "today"
    window_hours = None
    if args.today:
        view = "today"
    elif args.next is not None:
        view = "next"
        window_hours = args.next
    elif args.attention:
        view = "attention"
    elif args.completed:
        view = "completed"
    elif args.all:
        view = "all"

    page = await service.list(
        workspace_key=None, view=view, window_hours=window_hours,
        limit=args.limit, offset=args.offset, trace_id="cli",
    )

    if args.json:
        print(json.dumps(page.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    if not page.items:
        print(f"当前没有符合条件的日程安排。")
        return 0

    print(f"{'TIME':<20} {'SOURCE':<10} {'STATUS':<12} TITLE")
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

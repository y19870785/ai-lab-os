"""Reschedule a persisted Reminder through the shared management service."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from cli.runtime import reschedule_reminder


async def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m cli reminder-reschedule")
    parser.add_argument("reminder_id")
    parser.add_argument("--scheduled-for", required=True)
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--idempotency-key", default="")
    parser.add_argument("--json", action="store_true", dest="as_json")
    options = parser.parse_args(args)
    try:
        scheduled_for = datetime.fromisoformat(options.scheduled_for)
    except ValueError as exc:
        parser.error(f"invalid --scheduled-for: {exc}")
    if scheduled_for.tzinfo is None or scheduled_for.utcoffset() is None:
        parser.error("--scheduled-for must include a timezone offset")
    result = await reschedule_reminder(
        options.reminder_id,
        scheduled_for=scheduled_for,
        timezone_name=options.timezone,
        idempotency_key=options.idempotency_key,
    )
    if options.as_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    print("Reminder rescheduled")
    print(f"Reminder ID: {result.current.reminder_id}")
    print(f"Title: {result.current.task_title}")
    print(f"Previous time: {result.previous_scheduled_for.isoformat()}")
    print(f"New time: {result.current.scheduled_for.isoformat()}")
    print(f"Current status: {result.current.status}")

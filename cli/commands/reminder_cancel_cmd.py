"""Cancel a persisted Reminder through the shared management service."""

from __future__ import annotations

import argparse
import json

from cli.runtime import cancel_reminder


async def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m cli reminder-cancel")
    parser.add_argument("reminder_id")
    parser.add_argument("--json", action="store_true", dest="as_json")
    options = parser.parse_args(args)
    result = await cancel_reminder(options.reminder_id)
    if options.as_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return
    print("Reminder cancelled")
    print(f"Reminder ID: {result.current.reminder_id}")
    print(f"Title: {result.current.task_title}")
    print(f"Previous status: {result.previous_status}")
    print(f"Current status: {result.current.status}")
    print(f"Scheduled time: {result.current.scheduled_for.isoformat()}")

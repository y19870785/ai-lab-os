"""Query a durable in-app Reminder status through the Composition Root."""

from __future__ import annotations

import json
import argparse

from cli.runtime import query_reminder_status


async def run(args: list[str]) -> None:
    parser = argparse.ArgumentParser(prog="python -m cli reminder-status")
    parser.add_argument("reminder_id")
    parser.add_argument("--human", action="store_true")
    options = parser.parse_args(args)
    status = await query_reminder_status(options.reminder_id)
    if not options.human:
        print(json.dumps(status.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
        return
    print(f"Reminder ID: {status.reminder_id}")
    print(f"Task: {status.task_title}")
    print(f"Status: {status.status}")
    print(f"Scheduled for: {status.scheduled_for.isoformat()}")
    print(f"Timezone: {status.timezone}")
    print(f"Scheduler Job: {status.scheduler_job_id or '-'} ({status.scheduler_status or '-'})")
    print(f"Occurrence: {status.occurrence_id or '-'} ({status.occurrence_status or '-'})")
    print(f"Triggered at: {status.triggered_at.isoformat() if status.triggered_at else '-'}")
    print(f"Last failure: {status.last_failure.code if status.last_failure else '-'}")
    print(f"Retryable: {status.retryable}")

"""Query a durable in-app Reminder status through the Composition Root."""

from __future__ import annotations

import json

from cli.runtime import query_reminder_status


async def run(args: list[str]) -> None:
    if len(args) != 1:
        raise SystemExit("Usage: python -m cli reminder-status <reminder_id>")
    status = await query_reminder_status(args[0])
    print(json.dumps(status.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))

"""Unified Inbox CLI commands."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from cli.runtime import execute_inbox_operation
from core.user_tasks import UserTaskPriority


def _aware_datetime(parser: argparse.ArgumentParser, value: str, option: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        parser.error(f"invalid {option}: {exc}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parser.error(f"{option} must include a timezone offset")
    return parsed


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")


async def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli inbox")
    commands = parser.add_subparsers(dest="operation", required=True)

    add_parser = commands.add_parser("add")
    add_parser.add_argument("content")
    _add_json(add_parser)

    list_parser = commands.add_parser("list")
    list_parser.add_argument(
        "--status", choices=("pending", "resolved", "dismissed", "all"), default="pending"
    )
    list_parser.add_argument("--limit", type=int, default=50)
    list_parser.add_argument("--offset", type=int, default=0)
    _add_json(list_parser)

    show_parser = commands.add_parser("show")
    show_parser.add_argument("item_id")
    _add_json(show_parser)

    task_parser = commands.add_parser("resolve-task")
    task_parser.add_argument("item_id")
    task_parser.add_argument("--title", required=True)
    task_parser.add_argument("--description", default="")
    task_parser.add_argument("--due-at")
    task_parser.add_argument(
        "--priority", choices=tuple(item.value for item in UserTaskPriority), default="medium"
    )
    _add_json(task_parser)

    reminder_parser = commands.add_parser("resolve-reminder")
    reminder_parser.add_argument("item_id")
    reminder_parser.add_argument("--title", required=True)
    reminder_parser.add_argument("--description", default="")
    reminder_parser.add_argument("--scheduled-at", required=True)
    reminder_parser.add_argument("--timezone", default="Asia/Shanghai")
    reminder_parser.add_argument(
        "--priority", choices=tuple(item.value for item in UserTaskPriority), default="medium"
    )
    _add_json(reminder_parser)

    work_log_parser = commands.add_parser("resolve-work-log")
    work_log_parser.add_argument("item_id")
    work_log_parser.add_argument("--title", required=True)
    work_log_parser.add_argument("--description", default="")
    _add_json(work_log_parser)

    note_parser = commands.add_parser("resolve-note")
    note_parser.add_argument("item_id")
    _add_json(note_parser)

    dismiss_parser = commands.add_parser("dismiss")
    dismiss_parser.add_argument("item_id")
    _add_json(dismiss_parser)

    options = parser.parse_args(args)
    operation = options.operation
    values = vars(options).copy()
    values.pop("operation")
    as_json = values.pop("as_json")

    if "item_id" in values:
        values["inbox_item_id"] = values.pop("item_id")
    if operation == "resolve-task":
        values["priority"] = UserTaskPriority(values["priority"])
        if values["due_at"]:
            values["due_at"] = _aware_datetime(parser, values["due_at"], "--due-at")
        else:
            values.pop("due_at")
    elif operation == "resolve-reminder":
        values["priority"] = UserTaskPriority(values["priority"])
        values["scheduled_at"] = _aware_datetime(
            parser, values["scheduled_at"], "--scheduled-at"
        )
        values["timezone_name"] = values.pop("timezone")

    result = await execute_inbox_operation(operation, **values)
    if as_json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    if operation == "list":
        if not result.items:
            print("收件箱中没有符合条件的记录。")
        for item in result.items:
            print(f"{item.id}  {item.status.value}  {item.content}")
        return 0

    print(f"{result.id}  {result.status.value}  {result.content}")
    if result.resolved_target_id:
        print(f"target: {result.resolved_target_id}")
    return 0

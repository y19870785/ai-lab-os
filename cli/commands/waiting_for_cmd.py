"""Canonical Waiting-For CLI commands."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from cli.runtime import execute_waiting_for_operation
from core.waiting_for import WaitingForView


def _aware_datetime(parser: argparse.ArgumentParser, value: str, option: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        parser.error(f"invalid {option}: {exc}")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parser.error(f"{option} must include a timezone offset")
    return parsed


def _common_mutation(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("waiting_for_id")
    parser.add_argument("--expected-revision", type=int, required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("--json", action="store_true", dest="as_json")


async def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli waiting-for")
    commands = parser.add_subparsers(dest="operation", required=True)

    create = commands.add_parser("create")
    create.add_argument("--subject", required=True)
    create.add_argument("--waiting-on", required=True)
    create.add_argument("--context", default="")
    create.add_argument("--expected-by")
    create.add_argument("--next-review-at")
    create.add_argument("--timezone", default="UTC")
    create.add_argument("--json", action="store_true", dest="as_json")

    listing = commands.add_parser("list")
    listing.add_argument(
        "--view",
        choices=tuple(value.value for value in WaitingForView),
        default="open",
    )
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)
    listing.add_argument("--json", action="store_true", dest="as_json")

    show = commands.add_parser("show")
    show.add_argument("waiting_for_id")
    show.add_argument("--json", action="store_true", dest="as_json")

    history = commands.add_parser("history")
    history.add_argument("waiting_for_id")
    history.add_argument("--limit", type=int, default=100)
    history.add_argument("--offset", type=int, default=0)
    history.add_argument("--json", action="store_true", dest="as_json")

    for name in ("follow-up", "snooze", "resolve", "cancel", "reopen"):
        command = commands.add_parser(name)
        _common_mutation(command)
        if name in {"follow-up", "snooze", "reopen"}:
            command.add_argument("--next-review-at")

    options = parser.parse_args(args)
    values = vars(options).copy()
    operation = values.pop("operation")
    as_json = values.pop("as_json")

    for key in ("expected_by", "next_review_at"):
        if key in values and values[key]:
            values[key] = _aware_datetime(parser, values[key], f"--{key.replace('_', '-')}")
        elif key in values:
            values.pop(key)
    if operation in {"follow-up", "snooze", "resolve", "cancel", "reopen"}:
        if operation == "resolve":
            values["resolution_note"] = values.pop("note")

    result = await execute_waiting_for_operation(operation, **values)
    payload = result.model_dump(mode="json")
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    if operation in {"list", "history"}:
        if not result.items:
            print("没有符合条件的 Waiting-For 记录。")
        for item in result.items:
            label = getattr(item, "subject", item.event_type.value)
            print(f"{item.id}  {label}")
        return 0
    item = getattr(result, "item", result)
    print(f"ID: {item.id}")
    print(f"status: {item.status.value}")
    print(f"subject: {item.subject}")
    print(f"waiting_on: {item.waiting_on}")
    print(f"revision: {item.revision}")
    print(f"expected_by: {item.expected_by or '-'}")
    print(f"next_review_at: {item.next_review_at or '-'}")
    if hasattr(result, "event"):
        print(f"event: {result.event.event_type.value}")
    return 0

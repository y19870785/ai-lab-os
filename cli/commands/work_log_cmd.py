"""Canonical Work Log CLI commands."""

from __future__ import annotations

import argparse
import json
from datetime import datetime

from cli.runtime import execute_work_log_operation
from core.work_log import (
    WorkLogCreateCommand,
    WorkLogQuery,
    WorkLogSource,
    WorkLogStatus,
)
from core.workspace.models import WorkspaceKey


def _add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tenant-id", default="default")
    parser.add_argument("--workspace-id", default="default")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--json", action="store_true")


def _workspace(options) -> WorkspaceKey:
    return WorkspaceKey(
        tenant_id=options.tenant_id,
        workspace_id=options.workspace_id,
        namespace=options.namespace,
        trace_id="cli",
    )


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli work-log")
    commands = parser.add_subparsers(dest="operation", required=True)

    create = commands.add_parser("create")
    create.add_argument("subject")
    create.add_argument("--raw-text")
    create.add_argument("--occurred-at")
    create.add_argument("--timezone")
    create.add_argument("--target")
    create.add_argument(
        "--status",
        choices=[item.value for item in WorkLogStatus],
        default=WorkLogStatus.COMPLETED.value,
    )
    create.add_argument("--tag", action="append", default=[])
    _add_workspace(create)

    listing = commands.add_parser("list")
    listing.add_argument("--date-from")
    listing.add_argument("--date-to")
    listing.add_argument("--target")
    listing.add_argument("--tag", action="append", default=[])
    listing.add_argument("--status", choices=[item.value for item in WorkLogStatus])
    listing.add_argument("--text")
    listing.add_argument("--context-ref")
    listing.add_argument("--limit", type=int, default=50)
    listing.add_argument("--offset", type=int, default=0)
    _add_workspace(listing)

    show = commands.add_parser("show")
    show.add_argument("work_log_id")
    _add_workspace(show)

    options = parser.parse_args(args)
    workspace = _workspace(options)
    if options.operation == "create":
        result = await execute_work_log_operation(
            "create",
            workspace_key=workspace,
            command=WorkLogCreateCommand(
                subject=options.subject,
                raw_text=options.raw_text or options.subject,
                occurred_at=_datetime(options.occurred_at),
                timezone=options.timezone,
                target=options.target,
                status=options.status,
                tags=options.tag,
                source=WorkLogSource.CLI,
            ),
        )
    elif options.operation == "list":
        result = await execute_work_log_operation(
            "list",
            workspace_key=workspace,
            query=WorkLogQuery(
                date_from=_datetime(options.date_from),
                date_to=_datetime(options.date_to),
                target=options.target,
                tags=options.tag,
                status=options.status,
                text=options.text,
                context_ref=options.context_ref,
                limit=options.limit,
                offset=options.offset,
            ),
        )
    else:
        result = await execute_work_log_operation(
            "show",
            workspace_key=workspace,
            work_log_id=options.work_log_id,
        )

    if options.json:
        print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0
    if options.operation == "list":
        if not result.items:
            print("当前没有符合条件的工作记录。")
        for item in result.items:
            print(
                f"{item.occurred_at.isoformat()} {item.id} "
                f"[{item.status.value}] {item.subject}"
            )
        print(
            f"显示 {result.count} 条，offset={result.offset}，"
            f"has_more={result.has_more}"
        )
    else:
        print(
            f"{result.id}\n{result.occurred_at.isoformat()} "
            f"[{result.status.value}]\n{result.subject}\n{result.raw_text}"
        )
    return 0

"""Direct, read-only Daily Review CLI."""

from __future__ import annotations

import argparse
import json

from cli.runtime import query_daily_review


async def run(args: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m cli daily-review")
    parser.add_argument("--date", required=True, choices=("today", "yesterday"))
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--tenant-id")
    parser.add_argument("--workspace-id")
    parser.add_argument("--namespace")
    parser.add_argument("--session-id")
    parser.add_argument("--agent-id")
    parser.add_argument("--json", action="store_true", dest="as_json")
    options = parser.parse_args(args)

    review, presentation = await query_daily_review(
        review_date=options.date,
        limit=options.limit,
        offset=options.offset,
        tenant_id=options.tenant_id,
        workspace_id=options.workspace_id,
        namespace=options.namespace,
        session_id=options.session_id,
        agent_id=options.agent_id,
    )
    if options.as_json:
        print(
            json.dumps(
                review.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(presentation)
    return 0

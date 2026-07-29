"""Safe Local Daily Profile diagnostics."""

from __future__ import annotations

import json

from core.system import load_system_settings


def run(args: list[str]) -> int:
    require_local_daily = args == ["--require-local-daily"]
    if args and not require_local_daily:
        raise SystemExit("usage: python -m cli profile [--require-local-daily]")
    settings = load_system_settings()
    if require_local_daily and settings.profile_name != "local-daily":
        raise SystemExit("Local Daily Profile is required")
    print(json.dumps(settings.safe_summary(), ensure_ascii=False, indent=2))
    return 0

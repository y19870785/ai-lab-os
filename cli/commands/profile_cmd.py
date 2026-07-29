"""Safe Local Daily Profile diagnostics."""

from __future__ import annotations

import json

from core.system import load_system_settings


def run(args: list[str]) -> int:
    if args:
        raise SystemExit("profile does not accept positional arguments")
    settings = load_system_settings()
    print(json.dumps(settings.safe_summary(), ensure_ascii=False, indent=2))
    return 0

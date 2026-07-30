"""Safe Local Daily Profile diagnostics."""

from __future__ import annotations

import json
import uuid

from core.errors import (
    ErrorCategory,
    FailureException,
    FailureInfo,
)
from core.system import load_system_settings


def run(args: list[str]) -> int:
    require_local_daily = args == ["--require-local-daily"]
    if args and not require_local_daily:
        raise SystemExit("usage: python -m cli profile [--require-local-daily]")
    try:
        settings = load_system_settings()
    except ValueError as exc:
        raise FailureException(FailureInfo(
            code="config.profile_invalid",
            category=ErrorCategory.VALIDATION,
            message="Local Daily Profile configuration is invalid",
            component="profile",
            operation="load",
            trace_id=f"trace_profile_{uuid.uuid4().hex}",
            retryable=False,
            details={"cause_type": type(exc).__name__},
        )) from None
    if require_local_daily and settings.profile_name != "local-daily":
        raise SystemExit("Local Daily Profile is required")
    print(json.dumps(settings.safe_summary(), ensure_ascii=False, indent=2))
    return 0

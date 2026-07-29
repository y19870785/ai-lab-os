"""Compatibility alias for ``work-log create``."""

from cli.runtime import execute_work_log_operation
from cli.workspace import workspace_from_settings
from core.system import load_system_settings
from core.work_log import WorkLogSource


async def run(args):
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli log <工作内容>")
        return
    record = await execute_work_log_operation(
        "create",
        workspace_key=workspace_from_settings(load_system_settings()),
        subject=user_input[:500],
        raw_text=user_input,
        source=WorkLogSource.CLI,
    )
    print(f"[OK] {record.id} {record.subject}")

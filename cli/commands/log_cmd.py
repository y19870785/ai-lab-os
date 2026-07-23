"""Compatibility alias for ``work-log create``."""

from core.work_log import WorkLogCreateCommand, WorkLogSource
from core.workspace.models import WorkspaceKey

from cli.runtime import execute_work_log_operation


async def run(args):
    user_input = " ".join(args) if args else ""
    if not user_input:
        print("Usage: python -m cli log <工作内容>")
        return
    record = await execute_work_log_operation(
        "create",
        workspace_key=WorkspaceKey(),
        command=WorkLogCreateCommand(
            subject=user_input[:500],
            raw_text=user_input,
            source=WorkLogSource.CLI,
        ),
    )
    print(f"[OK] {record.id} {record.subject}")

"""Work Log persistence protocol."""

from __future__ import annotations

from typing import Protocol

from core.work_log.models import WorkLogPage, WorkLogQuery, WorkLogRecord
from core.workspace.models import WorkspaceKey


class WorkLogRepository(Protocol):
    async def initialize(self) -> None: ...

    async def create(self, record: WorkLogRecord) -> WorkLogRecord: ...

    async def create_from_inbox(
        self, record: WorkLogRecord, reserved_id: str
    ) -> WorkLogRecord: ...

    async def get(
        self, workspace_key: WorkspaceKey, work_log_id: str
    ) -> WorkLogRecord: ...

    async def list(
        self, workspace_key: WorkspaceKey, query: WorkLogQuery
    ) -> WorkLogPage: ...

    async def close(self) -> None: ...

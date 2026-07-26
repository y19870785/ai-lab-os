"""Repository protocol for the canonical UserTask service boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from core.user_tasks.models import UserTask, UserTaskQuery
from core.workspace.models import WorkspaceKey


class UserTaskRepository(Protocol):
    async def initialize(self) -> None: ...

    async def close(self) -> None: ...

    async def health_check(self) -> dict[str, object]: ...

    async def create(self, task: UserTask) -> UserTask: ...

    async def get(
        self,
        workspace_key: WorkspaceKey,
        task_id: str,
    ) -> UserTask: ...

    async def list(
        self,
        workspace_key: WorkspaceKey,
        query: UserTaskQuery,
        *,
        as_of: datetime | None,
    ) -> list[UserTask]: ...

    async def update(
        self,
        workspace_key: WorkspaceKey,
        task: UserTask,
        expected_revision: int,
    ) -> UserTask: ...

"""Synchronous UserTask lifecycle coordination for Reminder recovery."""

from __future__ import annotations


class UserTaskReminderLifecycleCoordinator:
    def __init__(self, bridge) -> None:
        self._bridge = bridge

    async def after_user_task_terminal(self, task, trace_id: str = "") -> None:
        await self._bridge.cancel_for_task(task.id, trace_id)

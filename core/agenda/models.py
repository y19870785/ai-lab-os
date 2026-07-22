"""Read-model types for the Daily Agenda."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgendaItemSource(str, Enum):
    USER_TASK = "user_task"
    REMINDER = "reminder"
    WORK_LOG = "work_log"
    WAITING_FOR = "waiting_for"


class AgendaItemKind(str, Enum):
    ACTION = "action"
    EVENT = "event"
    ATTENTION = "attention"
    COMPLETED = "completed"


class AgendaView(str, Enum):
    TODAY = "today"
    NEXT = "next"
    ATTENTION = "attention"
    COMPLETED = "completed"
    ALL = "all"


_KIND_PRIORITY = {
    AgendaItemKind.ACTION: 0,
    AgendaItemKind.ATTENTION: 1,
    AgendaItemKind.EVENT: 2,
    AgendaItemKind.COMPLETED: 3,
}

_SOURCE_PRIORITY = {
    AgendaItemSource.REMINDER: 0,
    AgendaItemSource.USER_TASK: 1,
    AgendaItemSource.WORK_LOG: 2,
    AgendaItemSource.WAITING_FOR: 3,
}


def kind_priority(kind: AgendaItemKind) -> int:
    return _KIND_PRIORITY.get(kind, 99)


def source_priority(source: AgendaItemSource) -> int:
    return _SOURCE_PRIORITY.get(source, 99)


class AgendaItem(BaseModel):
    id: str
    source: AgendaItemSource
    kind: AgendaItemKind
    title: str
    status: str
    scheduled_for: datetime | None = None
    occurred_at: datetime | None = None
    due_at: datetime | None = None
    timezone: str
    workspace_id: str
    source_id: str
    task_id: str | None = None
    reminder_id: str | None = None
    waiting_for_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgendaPage(BaseModel):
    items: list[AgendaItem]
    count: int
    limit: int
    offset: int
    has_more: bool
    timezone: str
    generated_at: datetime
    view: str
    window_start: datetime
    window_end: datetime

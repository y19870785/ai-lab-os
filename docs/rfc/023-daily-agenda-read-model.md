# RFC-023：Daily Agenda Read Model

Status: Accepted

## Problem
Users need a unified view of today's tasks, reminders, and completed work without querying multiple endpoints.

## Goals
- Aggregate Reminder, UserTask, and Work Log into a single read model
- Support `today`, `next`, `attention`, `completed`, and `all` views
- Workspace-isolated, timezone-aware, paginated

## Non-goals
- No new truth source or agenda database
- No LLM classification for agenda intent
- No background materialization

## Key decisions
- `DailyAgendaService` is the single aggregation boundary
- ReminderInbox pages are capped at 100 per call; a paginated adapter reads multiple pages
- All sources are sorted globally before applying the candidate cap (1200) and offset/limit
- Any source failure returns `agenda.query_failed` with structured failure details
- SP-012 reminder query expressions are preserved without semantic drift

## Views
- `today`: reminders scheduled today (all statuses except cancelled), active tasks with due_at in today window, today's work logs
- `next`: actionable reminders and tasks in the next N hours (default 3)
- `attention`: failed/retrying reminders and overdue tasks
- `completed`: triggered reminders and work logs within today
- `all`: full aggregation for debugging

## Known limitations
- Cross-source pagination is not a database snapshot
- Deep offsets may increase cost
- No LLM-based intent classification
- No external notification or Web UI

# ADR-049：Daily Agenda Read Model Boundary

Status: Accepted

## Decision
`DailyAgendaService` reads from existing ReminderInboxService, UserTaskService, and MemoryManager without introducing a new truth source or agenda-specific database.

## Consequences
- No agenda table or event journal
- Views are computed on demand
- Cross-SQLite aggregation is not a single transaction

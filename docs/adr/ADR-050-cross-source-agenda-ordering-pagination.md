# ADR-050：Cross-Source Agenda Ordering and Pagination

Status: Accepted

## Decision
All sources are read with bounded limits (Reminder: 100/page), normalized into `AgendaItem`, sorted globally by effective_time, kind_priority, source_priority, then source_id. The candidate cap (1200) is applied after sorting, and offset/limit are applied to the capped list.

## Consequences
- Stable ordering independent of source read order
- Not a database snapshot; concurrent writes may affect adjacent pages
- Deep offsets may scan more source pages

# ADR-051：Agenda Query Failure Semantics

Status: Proposed / SP-013 implementation candidate

## Decision
Each source (Reminder, UserTask, Work Log) is queried independently. If any source throws, `agenda.query_failed` is returned with `failed_source`, `source_code`, and `source_category` in the details. No partial results are returned.

## Consequences
- Fail-closed for any source failure
- The caller receives a single structured failure with trace_id
- Does not silently skip a failed source

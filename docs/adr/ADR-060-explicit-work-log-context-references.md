# ADR-060 — Explicit Work Log Context References

Status: Accepted

> Accepted architecture decision for the SP-018 planning baseline. It does not approve or start implementation.

## Context

A Work Log may refer to a UserTask, Reminder, Waiting-For or Inbox item. These targets live behind independent services and, in several cases, separate SQLite databases. Title matching, person matching or LLM inference would make associations non-deterministic and could cross Workspace boundaries.

## Decision

1. Work Log context associations are stored only when the caller supplies an explicit canonical target ID.
2. Supported prefixes are `ut_`, `rem_`, `wf_` and `inbox_`.
3. Each reference records `kind`, `target_id` and an optional bounded `relation`.
4. Kind and prefix must agree; malformed, unsupported or duplicate references fail closed.
5. Format validation is a strong create contract.
6. Cross-service existence is not a strong transactional contract and does not block Work Log creation.
7. No cross-database foreign key or transaction is claimed.
8. Read paths may perform best-effort resolution when the dependency is enabled and the target is visible in the same Workspace.
9. Disabled dependency yields `not_checked`; missing or Workspace-inaccessible target yields `unresolved` without disclosing target details.
10. A reference remains stored and visible when its target later disappears; it is never silently removed.
11. LLM output, title similarity, names, tags or free-text resemblance cannot create a context reference.
12. Query by context reference uses the exact canonical target ID and complete Work Log Workspace scope.

## Consequences

- Associations are reproducible and auditable.
- Work Log creation remains available when optional services are disabled.
- Stored references can outlive targets and require explicit unresolved presentation.
- Strong referential integrity is intentionally not promised across databases.

## Rejected alternatives

### LLM or fuzzy automatic linking

Rejected because it cannot provide deterministic intent, Workspace safety or stable replay.

### Synchronous mandatory target lookup

Rejected because optional disabled services would block otherwise valid Work Log creation and still could not provide an atomic cross-database guarantee.

### Cross-database foreign keys

Rejected because SQLite databases are independent truth boundaries and the project does not claim cross-database transactions.

## Implementation boundary

This ADR does not add fields, models, lookups, foreign keys, Schema changes or LLM behavior. It only fixes the future architecture decision.

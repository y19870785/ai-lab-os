# ADR-045: Actionable Reminder Inbox Semantics

**Status:** Proposed / SP-011 implementation candidate
**Date:** 2026-07-17

## Context

The existing `upcoming` filter means only that `scheduled_for >= now`. It correctly supports historical and diagnostic combinations, but it can include future cancelled reminders and therefore does not answer the product question "what needs attention next?"

## Decision

Add the explicit `pending` inbox view:

```text
status in (scheduled, retrying)
and scheduled_for >= now
```

The view is shared by API, CLI `reminders --pending`, and deterministic CEO Assistant phrases such as "查看待处理提醒". Existing no-parameter list behavior remains all-items for compatibility. Explicit combinations such as `status=cancelled&time_scope=upcoming` remain supported.

The phrase "查看我的提醒" uses the pending view and may summarize terminal counts separately. It does not create a Reminder or hide terminal records from explicit queries.

## Consequences

- Product-facing pending results exclude cancelled and triggered items.
- The lower-level time filter remains composable and backward compatible.
- Status aggregation remains centralized; no second public Reminder status enum is introduced.

# ADR-044: Deterministic Response and Provider Separation

**Status:** Accepted
**Date:** 2026-07-17

## Acceptance Record

- Accepted through SP-011
- PR #23
- Approved Head: `beb99115dd273a9fe55e86d21e65f714e7f7f52f`
- Merge Commit: `5c4b442b2b5c7f934ac381020ba8b310976d5d3a`
- Accepted Date: 2026-07-17

## Context

CEO Assistant previously appended provider-mode notices to every successful answer. Reminder parsing, listing, detail, cancellation, and rescheduling are deterministic service operations and do not call an LLM, so provider notices on those paths are inaccurate product output.

## Decision

Application responses produced entirely by deterministic Reminder handlers carry an internal deterministic marker. The common response assembly step checks that marker before adding Mock provider notices. Ordinary LLM chat keeps the existing notice in explicit Mock mode.

The distinction is made where the response is assembled, not by string replacement, route-specific cleanup, or presentation hiding. Deterministic handlers must only report fields returned by persisted services.

## Consequences

- Reminder answers are free of unrelated provider configuration text.
- Mock LLM behavior remains visible on actual LLM-backed chat paths.
- The marker is an application response concern and does not create a second provider mode or bypass provider failures.

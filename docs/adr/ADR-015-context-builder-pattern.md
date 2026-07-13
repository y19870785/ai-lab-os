# ADR-015: Context Builder Pattern

## Status
Accepted (2026-07-12)

## Decision
All prompt construction goes through ContextBuilder. No agent code concatenates prompt strings directly. ContextBuilder assembles: system prompt + memory context + knowledge context + user input.

## Rationale
- Single point of control for prompt construction
- Memory and knowledge injection is automatic
- Prompt templates are centralized and versioned

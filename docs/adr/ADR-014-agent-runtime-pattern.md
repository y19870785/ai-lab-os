# ADR-014: Agent Runtime Pattern

## Status
Accepted (2026-07-12)

## Decision
Agent execution uses a Runtime + Executor pattern. Runtime manages lifecycle and orchestration. Executor runs a single interaction cycle (context -> LLM -> tools -> memory).

## Rationale
- Separates lifecycle concerns from execution logic
- Executor is independently testable
- Runtime can be swapped for different execution strategies

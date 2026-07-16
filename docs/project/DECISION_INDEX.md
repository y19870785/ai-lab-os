# AI-Lab Decision Index —— 设计决策索引

> 冻结版本：v0.32.4 | 日期：2026-07-14

## RFC 列表

| 编号 | 标题 | 状态 |
|---|---|---|
| RFC-001 | Core Layer Architecture | Adopted |
| RFC-002 | Memory Layer Architecture | Adopted |
| RFC-003 | Agent Architecture | Adopted |
| RFC-004 | Knowledge Layer Architecture | Adopted |
| RFC-005 | Core Runtime Architecture | Adopted |
| RFC-006 | Provider Layer Architecture | Adopted |
| RFC-007 | Knowledge Layer Architecture (v2) | Adopted |
| RFC-008 | Agent Runtime Architecture | Adopted |
| RFC-009 | Tool Runtime Architecture | Adopted |
| RFC-010 | MCP Adapter Architecture | Adopted |
| RFC-011 | Workflow Engine Architecture | Adopted |
| RFC-012 | Scheduler Runtime | Adopted |
| RFC-013 | Task Runtime Architecture | Adopted |
| RFC-013 (dup) | Multi-Agent Architecture | Adopted |
| RFC-014 | Application Foundation | Adopted |
| RFC-015 | Reminder Scheduler Bridge | Adopted |

## ADR 列表

| 编号 | 标题 | 状态 |
|---|---|---|
| ADR-001 | Core Layer Package Structure | Adopted |
| ADR-002 | Message Bus Interface | Adopted |
| ADR-003 | Memory Layer Tech Stack | Adopted |
| ADR-004 | Memory Data Model | Adopted |
| ADR-005 | Agent Identity Model | Adopted |
| ADR-006 | Knowledge Storage Strategy | Adopted |
| ADR-007 | Decision Memory Model | Adopted |
| ADR-008 | Unified Memory API | Adopted |
| ADR-009 | Database Manager Lifecycle | Adopted |
| ADR-010 | Provider Registry Pattern | Adopted |
| ADR-011 | Model Agnostic Principle | Adopted |
| ADR-012 | Pipeline Architecture | Adopted |
| ADR-013 | Hybrid Retrieval | Adopted |
| ADR-014 | Agent Runtime Pattern | Adopted |
| ADR-015 | Context Builder Pattern | Adopted |
| ADR-016 | Tool Registry Pattern | Adopted |
| ADR-017 | Tool Sandbox Isolation | Adopted |
| ADR-018 | Adapter Pattern | Adopted |
| ADR-019 | Tool Invocation Pipeline | Adopted |
| ADR-020 | Workflow Runtime Pattern | Adopted |
| ADR-021 | Workflow State Machine | Adopted |
| ADR-022 | Scheduler Pattern | Adopted |
| ADR-023 | Trigger Design | Adopted |
| ADR-024 | Agent Coordination Pattern | Adopted |
| ADR-024 (dup) | Task Runtime Pattern | Adopted |
| ADR-025 | Agent Message Bus | Adopted |
| ADR-025 (dup) | Task Dependency Design | Adopted |
| ADR-026 | Application Context | Adopted |
| ADR-027 | Workspace Isolation | Adopted |
| ADR-028 | Unified Application Runtime | Adopted |
| ADR-029 | Memory SQLite Connection Ownership | Adopted |
| ADR-030 | Canonical UserTask Domain | Adopted |
| ADR-031 | Scheduler Action Handler | Adopted |
| ADR-032 | Reminder Effectively-Once Occurrence | Adopted |

**总计：RFC 文件 21 篇（含历史编号重复），ADR 文件 43 篇（含历史编号重复）**

| ADR-033 | API Authentication Mechanism | Accepted | 2026-07-15 |
| ADR-034 | CORS Allowlist Policy | Accepted | 2026-07-15 |
| RFC-016 | Application API Security Boundary | Adopted | 2026-07-15 |

| RFC-017 | System Lifecycle Admission Gate | Adopted | 2026-07-16 |
| ADR-035 | System Lifecycle State Machine | Accepted | 2026-07-16 |
| ADR-036 | Shutdown Admission Policy | Accepted | 2026-07-16 |

| RFC-018 | Internal Work Admission Boundary | Adopted | 2026-07-16 |
| ADR-037 | Canonical Internal Work Entrypoint | Accepted | 2026-07-16 |
| ADR-038 | Admission Gate Dependency Injection | Accepted | 2026-07-16 |

| RFC-019 | Natural-Language Reminder Closure | Adopted | 2026-07-16 |
| ADR-039 | Natural-Language Reminder Orchestration Boundary | Accepted | 2026-07-16 |
| ADR-040 | Reminder Status Aggregation Contract | Accepted | 2026-07-16 |

> SP-007、SP-008 与 SP-009 均为 APPROVED / MERGED / RECONCILED / ARCHIVED。SP-009 通过 PR #19 以 Squash Commit `b1274d066cbc01053144cba8d5654a5f8c8a21da` 合并；下一任务尚未选择、无分支、无 PR、未启动。

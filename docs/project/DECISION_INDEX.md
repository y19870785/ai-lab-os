# AI-Lab Decision Index —— 设计决策索引

> 当前源码版本：v0.34.0 Alpha | 更新日期：2026-07-23

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

| RFC-020 | Reminder Inbox and User-Friendly Local Access | Adopted | 2026-07-16 |
| ADR-041 | Reminder Inbox Query Boundary | Accepted | 2026-07-16 |
| ADR-042 | Reminder List Status Consistency | Accepted | 2026-07-16 |

| RFC-021 | Reminder Management Closure | Adopted | 2026-07-17 |
| ADR-043 | Reminder Management Coordination Boundary | Accepted | 2026-07-17 |
| ADR-044 | Deterministic Response Provider Separation | Accepted | 2026-07-17 |
| ADR-045 | Actionable Reminder Inbox Semantics | Accepted | 2026-07-17 |

| RFC-022 | Natural-Language Intent Safety | Adopted | 2026-07-17 |
| ADR-046 | Deterministic Intent Effect Classification | Accepted | 2026-07-17 |
| ADR-047 | Read On Ambiguity And Explicit Write Commands | Accepted | 2026-07-17 |
| ADR-048 | User-Facing Failure Presentation Boundary | Accepted | 2026-07-17 |

| RFC-023 | Daily Agenda Read Model | Accepted | 2026-07-19 |
| ADR-049 | Daily Agenda Read Model Boundary | Accepted | 2026-07-19 |
| ADR-050 | Cross-Source Agenda Ordering and Pagination | Accepted | 2026-07-19 |
| ADR-051 | Agenda Query Failure Semantics | Accepted | 2026-07-19 |

| RFC-024 | Unified Inbox and Capture-to-Action | Accepted | 2026-07-19 |
| ADR-052 | Inbox Resolution Idempotency | Accepted | 2026-07-19 |
| ADR-053 | Inbox Source and Workspace Boundary | Accepted | 2026-07-19 |

| RFC-025 | Canonical Waiting-For Domain and Agenda Closure | Adopted | 2026-07-22 |
| ADR-054 | Model Waiting-For as a Separate Canonical Domain | Accepted | 2026-07-22 |
| ADR-055 | Daily Agenda Optional-Source Composition | Accepted | 2026-07-22 |
| RFC-026 | Follow-up Interaction and Capture Closure | Adopted | 2026-07-23 |
| ADR-056 | Deterministic Follow-up Interaction Boundary | Accepted | 2026-07-23 |
| ADR-057 | Inbox-to-Waiting-For Resolution Saga | Accepted | 2026-07-23 |
| RFC-027 | Work Log Query Boundary and Context Closure | Adopted | 2026-07-23 |
| ADR-058 | WorkLogService over Existing Episodic Storage | Accepted | 2026-07-23 |
| ADR-059 | Canonical Work Log ID and Read-Only Legacy Projection | Accepted | 2026-07-23 |
| ADR-060 | Explicit Work Log Context References | Accepted | 2026-07-23 |

> SP-010 已通过 PR #21 以 Squash Commit `af437afc32dcb17da68d600d6840ec94c8cbe681` 合并，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。

> SP-007 至 SP-011 均为 APPROVED / MERGED / RECONCILED / ARCHIVED。SP-011 手工验收记录为 Reminder Core PASSED、Natural-language Reminder UX CONDITIONALLY PASSED；SP-012 已合并并完成对账。

> SP-014、SP-014B、SP-015、SP-015A、SP-015R、SP-016 与 SP-017 已完成并封存；ACC-014 A～L、ACC-016 A～J、ACC-017 A～O 全部 PASSED / FINAL。SP-018 已在 Draft Head 实现并通过自动化验证：RFC-027 为 Adopted，ADR-058～ADR-060 为 Accepted，ACC-018 仍未执行；SP-018 尚未合并，SP-019 未批准、未启动。

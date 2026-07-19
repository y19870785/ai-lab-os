# 架构状态 —— v0.33.0（post-release main）

> SP-010 Reminder Inbox 已通过 PR #21 合并，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。`ReminderInboxService` 复用 ADR-040 聚合并由 Composition Root 统一持有；RFC-020 已 Adopted，ADR-041/042 已 Accepted。跨 SQLite 聚合不是快照事务。

> SP-011 Reminder Management Closure 已通过 PR #23 合并并完成治理对账，状态为 APPROVED / MERGED / RECONCILED / ARCHIVED。Composition Root-owned `ReminderManagementService` 复用现有 Bridge Saga，并将确定性 Reminder 响应与 Provider 提示分离。RFC-021 已 Adopted，ADR-043/044/045 已 Accepted。跨数据库原子事务、外部通知、Recurring Reminder 与 Web UI 仍未实现。

> SP-012 为 APPROVED / MERGED / RECONCILED / ARCHIVED。实现收紧 CEO Assistant 与 CLI 的确定性意图边界：查询采用显式 `read` effect，写入要求明确命令或已发生动作，Reminder FailureInfo 由应用层集中呈现中文文案。RFC-022 已 Adopted，ADR-046/047/048 已 Accepted；查询兼容性由 SP-013 场景 H 实际覆盖。

> SP-013 Daily Agenda 为 APPROVED / MERGED / MANUAL_ACCEPTANCE_PASSED。Feature、post-merge reconciliation 与 SP-013B CLI workspace 修复均已进入 `main`。CI-001 已提供 Python 3.12 Pull Request / `main` push / manual Quality Gate。

## 当前十一层架构

```
Governance → Application → Coordination → Task → Scheduler → Workflow →
Agent → Knowledge → Provider → Memory → Core
```

Coordination 是独立层。Tool Runtime 与 MCP Adapter 是 Agent/Provider 边界内的支撑子系统，
不会被重复计入当前十一层的层数。

## 完整层级视图

```
┌─────────────────────────────────────────────┐
│               Governance                    │
├─────────────────────────────────────────────┤
│              Application                    │
├─────────────────────────────────────────────┤
│             Coordination                    │
├─────────────────────────────────────────────┤
│            Task Runtime                     │  ← 统一任务编排中心
├─────────────────────────────────────────────┤
│           Scheduler Runtime                 │  ← 定时/触发调度
├─────────────────────────────────────────────┤
│          Workflow Engine                    │  ← 状态机 + Checkpoint
├─────────────────────────────────────────────┤
│           Agent Runtime                     │  ← ContextBuilder + Executor
├─────────────────────────────────────────────┤
│          Knowledge Layer                    │  ← Ingestion → Chunk → Retrieval
├─────────────────────────────────────────────┤
│          Provider Layer                     │  ← LLM / Embedding / Vector / Storage
├─────────────────────────────────────────────┤
│         Memory (4 层)  │   Core (Bus + DB)  │
└─────────────────────────────────────────────┘
```

Supporting subsystems: Tool Runtime（Sandbox / Permissions / Audit）与 MCP Adapter（协议转换）。

## Task Runtime

```
TaskRuntime
  ├── TaskManager (CRUD / 统计)
  ├── TaskRegistry (注册 / 查找)
  ├── TaskPlanner (Rule / LLM / Tree — 策略模式)
  ├── TaskStateMachine (11 状态)
  ├── DependencyResolver (跨 Task 依赖)
  ├── ContextManager (跨 Workflow 共享上下文)
  ├── CheckpointManager (快照 / 恢复)
  └── EventBus Integration (9 种 Task 事件)
```

## Scheduler Runtime

```
SchedulerRuntime (Tick-loop)
  ├── TriggerEngine (Cron / Interval / One-shot / Manual / Event)
  ├── SQLite CAS Claim + Persistent JobRun
  ├── ActionHandlerRegistry → Workflow / Reminder Handler
  ├── SchedulerRegistry
  ├── SchedulerPersistence (SQLite, independent owner)
  └── ReminderSchedulerBridge → reminders.db / reconciliation
```

## Workflow Engine

```
WorkflowRuntime
  ├── WorkflowRegistry
  ├── WorkflowExecutor
  ├── WorkflowPlanner (策略模式)
  ├── WorkflowStateMachine (11 状态)
  ├── WorkflowCheckpoint (快照 / 恢复)
  └── EventBus Integration (9 种 Workflow 事件)
```

## 当前验证基线

GitHub Ubuntu Quality Gate（Python 3.12）当前为 `1096 passed, 6 skipped, 27 warnings`；
Ruff 仅检查本次变更的 Python 文件，pytest 显式排除 `tests/real`。Windows 本地基线为
`1102 passed, 5 deselected`。CI-002 与 QUALITY-001 仍是后续质量债务。

SP-005 合并前的 Windows 本地完整验证为 `888 passed, 27 warnings in 45.19s`。该结果不是 GitHub Actions 或跨平台 CI 记录。Scheduler / Reminder 已集成并验证，但默认关闭；外部通知、Recurring Reminder 与 Inbox 尚未实现。

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 System Lifecycle Admission Gate 与 SP-008 Internal Work Admission Boundary 均已 APPROVED / MERGED / RECONCILED / ARCHIVED。SP-008 通过 PR #16、Squash Commit `1858d4991379058948559cc96e2672df44e42b67` 将同一生命周期真相扩展到内部 Runtime、CEO Assistant、CLI 与 Scheduler producer，未在业务模块复制状态标志。

SP-008 合并前 Windows 本地 Python 3.12 验证为 `977 passed, 27 warnings in 49.17s`，零失败、零错误；这是历史记录，不是 GitHub Actions 或跨平台 CI 结果。

## SP-009 Natural-Language Reminder Closure

自然语言提醒闭环通过 Composition Root 注入 `TaskReminderIntentParser`、`Clock` 与 `NaturalLanguageReminderOrchestrator`，复用既有 Reminder Saga 和 Scheduler CAS/Occurrence 语义。站内聚合状态来自持久化组件。SP-009 已通过 PR #19 合并并完成对账：**APPROVED / MERGED / RECONCILED / ARCHIVED**；merge commit 为 `b1274d066cbc01053144cba8d5654a5f8c8a21da`。RFC-019 已 Adopted，ADR-039 与 ADR-040 已 Accepted。

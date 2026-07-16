# 架构状态 —— v0.33.0（post-release main）

## 当前十层架构

```
Application → Task → Scheduler → Workflow → Agent → Knowledge → Provider → Tool → Adapter → External
                                                                              ↑
                                                                         Memory / Core
```

## 完整层级视图

```
┌─────────────────────────────────────────────┐
│               Governance                    │
├─────────────────────────────────────────────┤
│              Application                    │
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
│           Tool Runtime                      │  ← Sandbox / Permissions / Audit
├─────────────────────────────────────────────┤
│           MCP Adapter                       │  ← 协议转换
├─────────────────────────────────────────────┤
│         Memory (4 层)  │   Core (Bus + DB)  │
└─────────────────────────────────────────────┘
```

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

SP-005 合并前的 Windows 本地完整验证为 `888 passed, 27 warnings in 45.19s`。该结果不是 GitHub Actions 或跨平台 CI 记录。Scheduler / Reminder 已集成并验证，但默认关闭；外部通知、Recurring Reminder 与 Inbox 尚未实现。

> SP-006 API Security Boundary: Integrated / Verified (Merged PR #12).

> SP-007 System Lifecycle Admission Gate: APPROVED / MERGED / RECONCILED / ARCHIVED。FastAPI 受保护业务路由的生命周期准入已进入 main（PR #14，Squash Commit `ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`）。SP-008 Internal Work Admission Boundary: implementation candidate / Draft PR / Awaiting ChatGPT review / Not merged；候选使用单一注入 gate，不在业务模块复制生命周期标志。

SP-008 候选的 Windows 本地 Python 3.12 验证为 `977 passed, 27 warnings in 49.17s`，零失败、零错误；不是 GitHub Actions 或跨平台 CI 结果。

# RFC-013: Task Runtime Architecture

**状态：** Accepted
**版本：** v0.22.0
**日期：** 2026-07-13

## 摘要

Task Runtime 是 AI-Lab 的统一任务编排中心，位于 Scheduler 和 Workflow 之上。它回答「为什么执行」和「谁负责整个任务生命周期」，管理多个 Workflow 的组合执行、跨 Workflow 共享上下文、以及完整的状态机生命周期。

## 动机

AI-Lab 当前可完成 `Scheduler → Workflow → Agent → Tool` 的单链路，但缺少一个统一层来编排多个 Workflow、管理任务间依赖、共享上下文。Task Runtime 填补这个空白，并为后续 Multi-Agent 提供基础。

## 架构

```
Application
      ↓
TaskRuntime（统一任务编排中心）
  ├── TaskManager（Task 生命周期）
  ├── TaskStateMachine（11 状态）
  ├── TaskPlanner（策略模式）
  ├── ContextManager（跨 Workflow 共享上下文）
  ├── DependencyResolver（任务间依赖）
  ├── CheckpointManager（任务级快照）
  └── EventBus（12 种事件）
      ↓
SchedulerRuntime → WorkflowRuntime → AgentRuntime → ToolRuntime
```

## Task 生命周期

```
CREATED → READY → RUNNING → COMPLETED / FAILED / TIMEOUT / CANCELLED
              ↘ PAUSED → RUNNING
              ↘ WAITING → RUNNING
    FAILED → RETRYING → RUNNING
    Any status → CANCELLED → DESTROYED
    COMPLETED / FAILED / TIMEOUT → DESTROYED
```

## 依赖方向

```
Application → Task → Scheduler → Workflow → Agent → Knowledge → Provider → Tool → Adapter → External
```

Task 永远不直接调用 Tool / Provider / MCP。

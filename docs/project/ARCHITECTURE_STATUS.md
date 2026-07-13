# 架构状态 —— v0.22.0

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
  ├── JobExecutor → WorkflowRuntime
  ├── SchedulerRegistry
  └── SchedulerPersistence (SQLite)
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

## 各模块测试数量

| Module | Tests |
|--------|-------|
| Core (Bus + DB + Logging) | 72 |
| Memory (4 层 + Consolidation) | 121 |
| Knowledge | 40 |
| Provider | 54 |
| Agent Runtime | 36 |
| Tool Runtime | 64 |
| Workflow | 51 |
| Scheduler | 48 |
| Task | 60 |
| Integration (E2E + MCP) | 46 |
| **Total** | **523** |

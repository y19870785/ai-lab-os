# RFC-017：系统生命周期准入门禁

## 状态

Adopted

## 采用记录

由 SP-007 实现，并通过 PR #14 合并。

Merge Commit：`ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Adoption Date：2026-07-16

## 背景

`SystemContainer` 过去使用 `_started`、`_starting` 与 `_stopped` 布尔值跟踪生命周期。
关闭期间仍可能准入新工作，使其访问部分已关闭组件；系统缺少统一准入门禁。

## 决策

1. 用 canonical `SystemLifecycleState` Enum 替换布尔 Flag；
2. 增加 `ensure_accepting_work()`，非 `READY` 时抛出 `FailureException`；
3. FastAPI 受保护业务路由依赖使用该 Gate；
4. Health Endpoint 通过 unguarded access 绕过 Gate；
5. `CREATED` 可以直接关闭到 `STOPPED`，不执行组件清理。

## 后果

- `DRAINING`/`STOPPED` 期间全部业务 API 返回 HTTP 503；
- Draining Response 包含 `Retry-After: 1`；
- `_shutdown_task` 保证并发 Shutdown 幂等；
- 不支持 Restart，禁止 `STOPPED -> STARTING`。

## 准入范围

SP-007 只覆盖通过 `get_system()` 与 `ensure_accepting_work()` 进入的 FastAPI 受保护业务
路由。直接 `ApplicationRuntime`、直接 `CEOAssistant` 和 CLI 入口不在 SP-007 范围；
这些路径当时没有注入准入 Callback，也不得被本文声称为已覆盖。

历史上候选 SP-008 负责定义规范内部执行边界，并在不复制 Lifecycle Flag 的前提下注入
Callback；其后续实际状态以 `project_state.json` 和相关采用记录为准。

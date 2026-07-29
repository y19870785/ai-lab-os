# ADR-036：关闭期间的工作准入策略

## 状态

Accepted

## 验收记录

由 SP-007 实现，并通过 PR #14 合并。

Merge Commit：`ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Accepted Date：2026-07-16

## 范围

SP-007 只在 FastAPI 受保护业务路由拒绝新工作。直接调用 `ApplicationRuntime`、
`CEOAssistant` 与 CLI 的执行路径明确不在范围内，并计划由候选 SP-008 处理。

## 背景

系统关闭期间，必须先拒绝新工作，再关闭组件。

## 决策

1. 关闭的第一个动作是转换到 `DRAINING`；
2. 业务准入门禁拒绝所有非 `READY` 状态；
3. 使用 `_shutdown_task` 保证并发关闭只有一个所有者；
4. `DRAINING` 与 `STOPPED` 期间 Health 与 Metrics 仍可访问；
5. 记录并报告清理失败，同时让所有组件都获得清理机会。

## 后果

- `DRAINING` 响应为 HTTP 503，带 `Retry-After: 1`；
- 组件清理失败会使最终状态变为 `FAILED`；
- `DatabaseManager` 最后关闭。

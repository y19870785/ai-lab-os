# ADR-035：系统生命周期状态机

## 状态

Accepted

## 验收记录

由 SP-007 实现，并通过 PR #14 合并。

Merge Commit：`ceb8ac4b120898d2d83dbe0e3afb4dd52dcb85ee`

Accepted Date：2026-07-16

## 范围

该状态机是 SP-007 中 `SystemContainer` 与 FastAPI 受保护路由准入的权威来源。
Application、CEO Assistant 和 CLI 的直接执行准入延期到候选 SP-008。

## 背景

系统需要一个统一的运行状态权威来源。

## 决策

使用 `LifecycleStateMachine`，状态包括 `CREATED`、`STARTING`、`READY`、`DRAINING`、
`STOPPED` 和 `FAILED`。状态转换由 `asyncio.Lock` 保护；非法转换抛出
`InvalidLifecycleTransitionError`。

## 后果

- 只有 `READY` 接受工作；
- `CREATED -> STOPPED` 是合法的未启动即关闭路径；
- `STOPPED` 后不支持重启。

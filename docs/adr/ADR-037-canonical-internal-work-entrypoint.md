# ADR-037：规范内部工作入口

## 状态

Accepted

## 验收记录

- 由 SP-008 Accepted；
- PR：#16；
- Merge Commit：`1858d4991379058948559cc96e2672df44e42b67`；
- Accepted Date：2026-07-16。

## 背景

新工作可通过直接 Application 调用、直接 CEO Assistant 调用、CLI 命令和 Scheduler
dispatch 进入。若每个下游 Runtime 都重新检查，系统进入 draining 前已被接受的工作将
无法正常完成。

## 决策

- `ApplicationRuntime.execute()` 是规范 Application 边界；
- 公开可调用的 `CEOAssistant.run()` 也必须经过门禁；
- CLI 业务命令通过 `ApplicationRuntime.execute()` 纳入，不重复检查；
- Scheduler due-job claim/dispatch 是独立生产者边界；
- 同一 Task 的嵌套调用是已接受工作的延续；detached child 调用规范入口属于新工作，
  必须重新准入；
- TaskRuntime、WorkflowRuntime、AgentRuntime、Reminder handler、Health、启动、关闭、
  清理、恢复和 Migration 不在准入范围；
- Alpha Assistant 的直接调用没有在生产组合根注册，因此不在范围。

## 后果

所有纳入范围的新工作在非 `READY` 状态都被拒绝；已在 `READY` 接受的同一 Task 下游工作
不需要第二次生命周期决策即可完成。普通 Child Task 不获得可复用 bypass；只有 Scheduler
拥有的 Job Task 是显式 spawned continuation。

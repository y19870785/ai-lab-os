# ADR-038：准入门禁依赖注入

## 状态

Accepted

## 验收记录

- 由 SP-008 Accepted；
- PR：#16；
- Approved Head：`536d1563baaecf5d50eeefc93dfdb0dbbfe3c659`；
- Merge Commit：`1858d4991379058948559cc96e2672df44e42b67`；
- Accepted Date：2026-07-16。

## 背景

业务模块需要生命周期准入能力，但不应依赖 `SystemContainer`，也不应重复生命周期错误映射。

## 决策

组合根创建一个 `LifecycleStateMachine` 和一个 `WorkAdmissionGate`，并将同一个 Gate
注入 `SystemContainer`、`ApplicationRuntime`、`CEOAssistant` 和 Scheduler。构造函数
只依赖狭窄的 `WorkAdmission` 合同，`SystemContainer.ensure_accepting_work()` 委托 Gate。

Gate 暴露同步的 accepted-work context，其 capability 与当前 `asyncio.Task` identity
绑定。同一 Task 嵌套可避免重复检查，并保持已接受工作。普通 Child Task 即使复制
`ContextVar` 也不会转移所有权，因此 detached child 必须重新准入。

Scheduler 使用同一窄合同，并且是唯一调用 `spawn_accepted_task()` 的组件。该方法为
Scheduler Job Task 创建新 capability，使已接受 Job 能在 `DRAINING` 后完成，但不授予
普通 Child Task bypass。测试独立组件必须显式使用 permissive 实现；生产构造没有隐式
permissive fallback。

`core.system.__init__` 的 lazy export 避免 package import cycle，并保持既有公开导入面。

## 后果

- 生产 Wiring 缺少准入依赖时失败关闭；
- 业务模块不导入或持有 `SystemContainer`；
- 生命周期 code 与 `FailureInfo` 构造保持集中；
- 准入过程没有 I/O、await、Lock wait 或外部副作用；
- Detached Task 无法把复制的 Context 转为准入 capability；
- Capability 传播显式限制在 Scheduler 拥有的 Job Task。

# RFC-018：内部工作准入边界

## 状态

Adopted

## 采用记录

- 由 SP-008 实现；
- 通过 PR #16 合并；
- Approved Head：`536d1563baaecf5d50eeefc93dfdb0dbbfe3c659`；
- Merge Commit：`1858d4991379058948559cc96e2672df44e42b67`；
- Adoption Date：2026-07-16。

## 背景

SP-007 在系统离开 `READY` 后拒绝新的 FastAPI 业务请求，但进程内直接调用仍可绕过
FastAPI Dependency 进入 `ApplicationRuntime`、`CEOAssistant` 或 Scheduler dispatch。
SP-008 在不新增第二个生命周期权威来源的前提下关闭该缺口。

## 目标

- 复用 `SystemContainer` Lifecycle State 与 SP-007 `FailureInfo` code；
- 只在最外层 canonical boundary 检查一次新工作；
- 保留转换到 `DRAINING` 前已接受的工作；
- 生产入口缺少准入注入时构造失败。

## 非目标

- In-flight counter、drain timeout、强制取消或等待全部工作；
- Initialization、Shutdown、Health、Diagnostics、Persistence 或 Cleanup Gate；
- 新产品行为、数据库变更或 Distributed Admission。

## 审计结论

| 路径 | 分类 | 决策 |
| --- | --- | --- |
| `ApplicationRuntime.execute()` | 直接 Application 工作 | canonical gated entrypoint |
| `CEOAssistant.run()` | 直接 Assistant 工作 | 经过 Gate，嵌套 Runtime dispatch 复用 scope |
| CLI 单次与交互命令 | 新用户工作 | 通过 `ApplicationRuntime.execute()` 覆盖 |
| Scheduler `_tick()` claim/dispatch | 后台 Producer | Claim 与创建 Task 前经过 Gate |
| Task/Workflow/Agent execution | 已接受下游工作 | 不重复 Gate |
| Reminder Bridge API operation | API 已准入工作 | 不重复 Gate |
| Reminder Scheduler handler | Scheduler 已准入工作 | 不重复 Gate |
| Recovery、Migration、Health、Start、Shutdown | 系统操作 | 排除 |
| Alpha Assistant 直接调用 | 生产组合外 Prototype | 注册为产品入口前排除 |

## 规范工作入口

纳入边界的是 `ApplicationRuntime.execute()`、直接 `CEOAssistant.run()` 和 Scheduler
due-job dispatch。CLI 不拥有第二个 Gate，因为每个业务命令都调用共享
`ApplicationRuntime`。

## 准入所有权与依赖注入

`WorkAdmissionGate` 拥有准入语义，读取 `SystemContainer` 持有的同一个
`LifecycleStateMachine`。`SystemContainer.ensure_accepting_work()` 委托该 Gate，因此
API 与内部调用方共享一个 Failure 合同。

组合根在构造 Runtime 前创建一个 Lifecycle 与一个 Gate，并显式注入
`ApplicationRuntime`、`CEOAssistant`、Scheduler 与 `SystemContainer`。生产构造缺少
Dependency 时失败；独立测试使用显式 test-only permissive admission object。

`core.system` 使用 lazy public export 避免
`applications.runtime -> core.system.admission -> core.system.__init__` Import Cycle。

## 已接受工作的语义

`WorkAdmissionGate.admit()` 创建与当前 `asyncio.Task` Identity 绑定的 capability。同一
Task 的嵌套调用复用 Scope，不重新读取 Lifecycle。外层在 `READY` 通过后，即使状态转到
`DRAINING`，同一工作的后续调用也不会被拒绝。

复制 Context 不会授予准入。普通 `asyncio.create_task()` 可能复制 `ContextVar`，但 Task
Identity 不匹配 Owner；它调用 canonical entrypoint 时仍被视为新工作并重新检查状态。

Scheduler 是狭窄例外：due job 准入并 claim 后，使用 `spawn_accepted_task()` 为执行 Task
创建显式所有权 capability。其他 Producer 不获得隐式 Child Task propagation。

## Scheduler 与 Reminder 边界

Scheduler 在 Claim due job 或创建后台 Task 前检查准入。生命周期拒绝会结束该 Tick，
且不 Claim、不持久化 Run、不调用 Handler、不发布 work-started Event。准入后只有
Scheduler 使用 `spawn_accepted_task()`。Reminder Bridge 没有后台 Tick；API operation
沿用 API 准入，Reminder handler 在 Scheduler 拥有的 accepted Task 内执行。

## 失败传播

内部调用方收到原始 `FailureException`，Code 集中定义：

- `CREATED` / `STARTING`：`system.not_ready`；
- `DRAINING`：`system.draining`；
- `STOPPED`：`system.stopped`；
- `FAILED`：`system.failed`。

全部使用 Category `unavailable`、Component `system.lifecycle`、Operation
`admit_request` 和 `retryable=true`。

## 已考虑的替代方案

- 在 API、Runtime、Assistant、Task 与 Workflow 层重复检查：拒绝，会在关闭开始后终止
  已接受工作；
- 将 `SystemContainer` 注入业务模块：拒绝，会形成宽依赖与构造 Cycle；
- 使用调用方控制的 Metadata Flag：拒绝，会导致意外绕过准入。

## 兼容性

SP-007 HTTP 503、`Retry-After: 1`、公开 Health Endpoint、API Authentication 和 CORS
保持不变。本文记录的历史产品版本为 `0.33.0`。

FastAPI 业务路由通过 `get_system()` 解析 `ApplicationRuntime`，先执行 API Lifecycle
检查；`ApplicationRuntime.execute()` 再在实际工作边界检查，从而关闭 Dependency 到
Execution 的 Race。准入后，下游同一 Task 复用 capability。

## 测试策略

测试覆盖所有 Lifecycle State、完整 `FailureInfo`、同一 Task exact-once nesting、
detached child isolation、已准入 in-flight completion、Scheduler claim/run rejection、
真实组合根 Identity Wiring、FastAPI Resolver allowlist、公开 `core.system` Import、
API/Security Regression、Lifecycle Regression 与完整测试套件。

## 已知限制

仍无进程级 in-flight counter、drain timeout、强制取消、多进程准入协调或零停机保证。
`spawn_accepted_task()` 仅限 Scheduler-owned continuation；Alpha Assistant Prototype、
Recovery 与 Migration Policy 明确不在该边界。

# ACC-020 本地日常运行闭环与 Review-to-Action 验收

- SP: SP-020
- Status: PLANNING_BASELINE / NOT_EXECUTED
- Manual acceptance: false
- Base: `934075ceefe39ede3c624b621b7673d62f6d06dd`
- Provider mode: future acceptance MUST use explicit mock/test
- Real Provider calls: MUST remain 0

本文件定义未来正式验收。当前没有任何场景已执行或通过；Planning Baseline、自动化测试
或 Draft PR 均不得被解释为 ACC-020 通过。

## 验收冻结与证据规则

执行前必须冻结 Approved Implementation Head、driver SHA-256、Python 版本、UTC/local
时间、source data root、restore data root、API process PID/port、配置摘要与所有命令
退出码。两个 data root 必须是不同绝对路径，且不得指向开发 checkout 的默认 `data/`。

每个 mutation 必须记录前后对象、canonical ID、workspace、持久化数据库事实，以及
该动作真实需要的 revision、idempotency key、durable claim/Saga、confirmation 与
相关 event 状态。不得把所有 mutation 套用同一 revision 规则。自然语言回复或 HTTP
2xx 不能单独作为成功依据。

driver/harness 错误必须标记 `INVALID_ACCEPTANCE_HARNESS` 并废弃该次运行；产品失败不得
通过改 driver、skip、xfail 或放宽断言掩盖。

`--prepare-only` 只能生成 `PREPARED_NOT_EXECUTED` 清单；所有未测量字段必须为
`null`、空集合或 `NOT_MEASURED`，不得把未执行命令、Provider call 或场景写成 0 /
PASS。非 prepare 模式必须实际启动 Uvicorn、执行入口与 A～V，不能退化为 no-op。
实施审查期间最多允许一次显式
`REHEARSAL / NOT_FORMAL_ACCEPTANCE`；它不冻结 Implementation Head，也不改变本文件
任何场景状态。

## ACC-020-A — Local Profile 启动与配置错误

验证显式 absolute `AI_LAB_DATA_DIR`、`AI_LAB_SQLITE_DIR`、IANA timezone、Provider
mode、feature flags、auth token 与 `127.0.0.1` bind。启动诊断显示最终非敏感配置而
不泄露 secret。

分别验证无效 timezone、`invalid` Provider、auth enabled 但 token 缺失、相对或冲突
data/sqlite root 均明确失败，且不会创建或连接另一个 fallback 数据目录。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-B — API readiness 与 health

启动真实 Uvicorn 进程。`/health/live` 证明进程存活，`/health/ready` 仅在唯一
`SystemContainer` READY 且 accepting_work 时成功。受保护业务路由无 token 失败、
正确 token 成功。记录 component health、provider mode 与 lifecycle。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-C — 真实数据创建

在 workspace A 通过真实入口创建 UserTask、Reminder、Inbox、Waiting-For 与 Work
Log；核对 `ut_`、`rem_`、`inbox_`、`wf_`、`wl_` canonical IDs、revision、workspace
evidence 及对应 SQLite 行。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-D — 每日议程

通过正式入口读取 today Agenda，确认启用 source 的真实对象出现、排序稳定、完整
WorkspaceKey 生效；读取不得产生新业务对象或 Provider call。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-E — 每日复盘 today / yesterday

通过 API 与正式 `daily-review` CLI 查询 today/yesterday。验证二者直接复用同一
`DailyReviewService` 合同，日期、timezone、DST、`as_of`、source status、canonical
ID、reason code、全局排序与分页一致。CLI `--json` 必须与 structured API facts 一致。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-F — 确定性操作提示

对固定 Review payload 重复生成 hints，结果与顺序必须完全相同。每条包含
`source_type/source_id/status/reason_code/allowed_action/required_arguments/
requires_revision/requires_idempotency_key/requires_confirmation/
requires_durable_claim/saga_contract/available_entrypoints`，并逐条证明对应真实
领域合同。`available_entrypoints` 只包含当前真实安全入口；每个 allowed action 至少
一个入口即可，不要求 API、CLI 与 CEO Assistant 三者齐全，也不得列出尚未存在的入口。
unsupported 组合不得伪造动作。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-G — UserTask 变更

分别验证：

- UserTask update 当前接受调用方 `expected_revision`，缺失时按当前兼容合同处理，
  stale revision 必须 fail closed；
- 历史 `/tasks/{id}/complete|cancel` API 仍兼容不提供调用方 revision；
- SP-020 Review-to-Action UserTask complete/cancel 已显式要求
  `expected_revision`；hint 声明 `requires_revision=true`，缺失或 stale revision
  必须 fail closed，包括对象已处于相同 terminal status 的情况。

另一 workspace 与模糊对象始终不得写入。成功以 `tasks.db` 当前对象
revision/status 为依据。成功 response 必须使用公共 `TaskResponse`，保留 `overdue`
派生值，不暴露 `legacy_source_id` 或内部 workspace metadata。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-H — Waiting-For 变更

依据 Review 中 canonical `wf_...` 执行 follow-up 或 resolve，并验证 history event 与
revision。另验证 snooze/cancel/reopen 的 action hint 只在真实状态允许时出现；stale
revision 与模糊表达不写入。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-I — Inbox 处理

依据 canonical `inbox_...` 将 pending item 显式 resolution 为 UserTask、Reminder、
Waiting-For、Work Log、Note 或 Dismiss 中的选定目标。验证 durable claim、target ID、
source resolution 状态、竞争与重试幂等；Waiting-For 缺少确认字段时不得创建目标。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-J — Review 更新

完成 G/H/I 后再次读取同一 date Review，验证已变更对象按 RFC-028 的事实窗口与
`as_of` 合同更新，pending Inbox 不再出现，且没有重复、遗漏、snapshot 或自动写入。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-K — 工作空间隔离

workspace B 使用相同查询、猜测到的 canonical ID 与 mutation 路径均不得看到或修改
workspace A 数据。API、CLI、CEO Assistant、Daily Review、Action Hint 与 canonical
service 使用相同完整 WorkspaceKey；不得回退到 default/unfiltered query。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-L — 零 LLM 调用

对启动、Agenda、Review、hint、canonical-ID actions、shutdown、restart 与 restore
安装 Provider spy。正式运行结束时 Provider calls 必须为 0；不得以 LLM 解析日期、
选择对象、生成 action 或执行 mutation。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-M — 零未确认副作用

对模糊写意图、缺 canonical ID、未知 status/reason、unsupported Work Log mutation，
以及缺少动作自身声明的必要参数做数据库、EventBus、Scheduler 和对象快照。仅当
Action Hint 声明 `requires_revision=true` 时，缺失或 stale revision 才必须 fail
closed；需要 idempotency key、durable claim/Saga 或 confirmation 的动作分别按自身
真实合同验收。所有未满足安全前置条件的操作前后状态必须相同；允许返回只读信息或
明确 preview/validation。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-N — EventBus 行为

纯 READ 与 Action Hint 不发布业务 mutation event。显式 canonical service mutation
只发布既有事件合同，event workspace/trace 与持久化对象一致；EventBus 停止后不再
接受 publish。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-O — Scheduler 与持续运行行为

真实启用 Scheduler/Reminder，验证 one-shot job、claim、run、Reminder 状态与
effectively-once 事实。重复 tick/并发 claim 不得重复执行。记录 scheduler health、
jobs、runs、claim token/revision 与 Reminder reconciliation。

持续运行证据不得只包含一次瞬时启动和关闭。driver 必须记录一个明确起止时间的运行
窗口，并至少覆盖：多个 Scheduler tick、一次真实 one-shot job 执行、一个空闲运行
窗口、周期性 health 快照、每次快照的 background task 状态与
`DatabaseManager.connection_count`。完成该窗口后，继续执行优雅关闭、新进程重启与
恢复验证。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-P — 优雅关闭

在真实 API 进程发出受控停止。验证先进入 draining、拒绝新工作、已接受工作按策略
收敛，Scheduler/background tasks、Reminder bridge、applications、services、
providers、EventBus 依次停止，最后 `DatabaseManager.connection_count=0`。关闭失败
必须进入 `shutdown_failures` 与 FAILED lifecycle。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-Q — 重复 shutdown 与 partial-start rollback

验证同一 shutdown 流程中当前两次 `SchedulerRuntime.shutdown()` 调用及外部重复
shutdown 都幂等：不重复业务执行、不泄漏 task/connection、不产生虚假 failure。
注入中途 startup failure，确认已初始化组件被回滚且 container 不可重启。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-R — 新进程重启恢复

关闭后使用同一 source data root 启动新 Uvicorn 进程和新 `SystemContainer`。验证
UserTask、Reminder、Scheduler jobs/runs、过期 claims、Inbox resolution Saga、
Waiting-For/history、Work Log、Agenda 与 Review 一致；不得重复执行、丢 job 或漂移。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-S — 完整数据目录静止备份

只有 P/Q 证明优雅关闭且 connection count 为 0 后，复制整个 source data root，包括
所有 SQLite、可能的 `-wal/-shm` 与可选目录。计算文件清单、size 与 SHA-256。不得在
进程运行时逐库复制并声称一致快照。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-T — 隔离恢复

将备份恢复到新的绝对 restore data root；原 source root 设为不可写或以 hash 监测。
使用显式 restore profile 与新进程启动，证明没有访问 source root 或 checkout 默认
`data/`。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-U — 恢复后对象与 Review 一致性

逐一核对 source 与 restore 的 canonical objects、revision、status、history、
scheduler jobs/runs、Reminder、Inbox claim/Saga、Waiting-For、Agenda 与
today/yesterday Review。允许 `generated_at/as_of` 随新进程时间变化；其余按正式时间
语义比较。restore 中追加写入不得改变 source hashes。

状态：PLANNING_BASELINE / NOT_EXECUTED

## ACC-020-V — FailureInfo、revision、idempotency 与 Saga

集中验证 config、auth、workspace、date/query、not-found、动作声明需要时的 missing
或 stale revision、unsupported state、dependency、persistence、scheduler、shutdown
与 restore failures
使用稳定 `FailureInfo` code/category/component/operation/trace_id/retryable，且 details
不含 secret。仅当 hint 声明 `requires_revision=true` 时才以缺失或 stale revision
失败关闭；idempotency key、Inbox durable resolution claim/Saga 与 confirmation
分别按动作真实合同验证。重放不得创建第二目标；Saga 中断后由新进程恢复或明确报告
可恢复状态。

状态：PLANNING_BASELINE / NOT_EXECUTED

## 正式执行门禁

执行 ACC-020 前必须同时满足：

```text
SP-020 Planning Baseline: APPROVED / MERGED / RECONCILED
SP-020 Implementation: EXPLICITLY APPROVED
Approved Implementation Head: FROZEN
Phase 0: PASSED
No unresolved Product PR or review thread
No version / tag / release side operation
```

SP-020 产品实施只需要一次明确 Owner 授权；Phase 0 是该授权内部的强制质量门禁，
通过后不需要再次授权。Phase 0 失败、触发停止条件、改变批准范围、拆分 Product SP
或引入新架构决策时，必须停止并重新请求 Owner 决策。

任何 Scheduler 重复执行/丢 job、shutdown 非幂等、数据目录静默漂移、跨 workspace
访问、未确认副作用、Provider call、无法隔离恢复或需要在线跨库快照，均为 STOP。

## 当前治理状态

```text
ACC-020:
PLANNING_BASELINE / NOT_EXECUTED

manual_acceptance:
false

All scenarios A-V:
PLANNING_BASELINE / NOT_EXECUTED
```

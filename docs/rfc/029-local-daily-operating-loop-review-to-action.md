# RFC-029 — Local Daily Operating Loop & Review-to-Action Closure

- Status: Adopted
- SP: SP-020
- Date: 2026-07-29
- Base: `934075ceefe39ede3c624b621b7673d62f6d06dd`
- Planning branch: `docs/sp-020-local-daily-operating-loop-planning`
- Planning review: APPROVED
- Planning PR: #53 / MERGED
- Planning merge commit: `fbd10fb5c4cd3913bb70d0c17cdd6df9de196625`
- Post-planning main Quality Gate: `30441534383` / SUCCESS
- Implementation: NOT APPROVED / NOT STARTED

## 当前问题

AI-Lab 已有 canonical UserTask、Reminder、Waiting-For、Inbox、Work Log、Daily
Agenda 与 Daily Review，但这些能力尚未形成一个可复现、可安全关闭、可重启并可恢复的
Windows 本地日常运行合同。当前主要缺口不是新的领域模型，而是入口、配置、动作提示、
生命周期与数据保护之间的闭环。

本 RFC 只定义未来实现边界。它不批准产品实现，不改变现有运行时行为。

## 真实用户日常场景

目标闭环为：

```text
启动 AI-Lab
→ readiness 通过
→ 捕获工作信息
→ 整理为 UserTask / Reminder / Waiting-For / Work Log
→ 查看 Daily Agenda
→ 查看 today / yesterday Daily Review
→ 依据 canonical source_id 选择明确动作
→ 委托现有 canonical domain service 执行
→ 再次查看 Review
→ 停止接收新工作并优雅关闭
→ 新进程从同一稳定数据目录恢复
→ 停机后备份完整 data directory
→ 在隔离目录恢复并验证
```

成功标准是用户可以连续、可靠地把 AI-Lab 用于真实日常工作，而不是新增接口数量。

## 已审计的当前事实

### 启动与配置

- `load_system_settings()` 默认以 `Path.cwd()` 为 project root，并只从该目录加载
  `.env`。
- 未显式设置时，`AI_LAB_DATA_DIR=<cwd>/data`，
  `AI_LAB_SQLITE_DIR=<data_dir>/sqlite`，
  `AI_LAB_CHROMA_DIR=<data_dir>/chroma`。
- 因而从不同 working directory 启动可能静默连接到不同数据目录。
- `AI_LAB_TIMEZONE` 默认为 `Asia/Shanghai`，并通过 `zoneinfo.ZoneInfo` 校验为
  IANA timezone。
- Provider mode 由显式 `AI_LAB_PROVIDER_MODE` 或凭据检测决定；真实进程不允许
  隐式退化为 mock。缺少或不完整的真实 Provider 配置会得到 `invalid` mode。
- API auth 默认开启；未设置 `AI_LAB_API_TOKEN` 时，API app 构造会明确失败。
- UserTask 与 Daily Review 默认开启；Reminder 与 Scheduler 默认关闭；Knowledge、
  Coordination 与 API 默认关闭。
- FastAPI lifespan 为长运行 API 进程持有一个 `SystemContainer`；CLI 单次命令通常
  创建、启动并在 `finally` 中关闭一个独立 `SystemContainer`。

### Daily Review

- `DailyReviewService` 只读取五个 canonical service，不拥有数据库、EventBus、
  lifecycle、snapshot 或独立 persistence，也不调用 Provider / LLM。
- 只支持 `today` 与 `yesterday`，并复用既有 timezone、DST、日期窗口、分类、去重、
  全局排序和分页合同。
- 每个 item 输出 canonical `source_type`、`source_id`、`status`、
  `reason_code`、`effective_at` 与 relevant time fields。
- API 与 CEO Assistant 使用同一个 `DailyReviewService`。
- 当前没有正式 `daily-review` CLI；`brief` CLI 只是通过 CEO Assistant 固定请求
  “今日简报”。
- 当前 Presenter 只展示事实与 canonical ID，不展示可执行动作。

### 生命周期与恢复

- `SystemContainer.start()` 在部分启动失败时调用 `shutdown()` 回滚。
- lifecycle 进入 draining 后，统一 admission gate 拒绝新工作；已接受的内部工作
  由各 runtime 的 shutdown 合同处理。
- `DatabaseManager.close_all()` 在其他组件停止后执行，并聚合关闭失败；
  `SystemContainer.shutdown_failures` 记录组件名，最终 lifecycle 为 `FAILED`。
- 同一个 container 不能从 STOPPED 或 FAILED 状态重启；恢复必须创建新 container。
- `SchedulerRuntime.initialize()` 释放过期 claim，并在 `auto_recover` 时载入 durable
  jobs；Reminder bridge 初始化时执行跨 reminders/scheduler 的 reconciliation。
- Inbox resolution 使用 durable claim / Saga；Waiting-For 与领域对象从 SQLite
  重新打开。
- 当前 `SystemContainer._run_shutdown()` 在同一流程中两次调用
  `SchedulerRuntime.shutdown()`。Scheduler 当前实现可重复取消 tick、清空 background
  tasks 并关闭 persistence，但 SP-020 Phase 0 必须用正式测试证明幂等，不能仅靠实现
  推断。
- 目前没有覆盖长时间运行、完整资源回收、进程级 restart recovery、完整 data
  directory 备份与隔离恢复的正式验收基线。

## Local Daily Profile

未来实现必须提供一个命名明确、可复现的 Windows Local Daily Profile。配置必须显式
显示并固定：

```text
AI_LAB_DATA_DIR=<stable absolute path>
AI_LAB_SQLITE_DIR=<stable absolute path under data dir>
AI_LAB_TIMEZONE=<explicit IANA timezone>
AI_LAB_PROVIDER_MODE=mock|test|real (explicit; acceptance uses mock/test)
AI_LAB_ENABLE_USER_TASKS=true
AI_LAB_ENABLE_DAILY_REVIEW=true
AI_LAB_ENABLE_REMINDERS=true
AI_LAB_ENABLE_SCHEDULER=true
AI_LAB_ENABLE_KNOWLEDGE=false
AI_LAB_ENABLE_COORDINATION=false
AI_LAB_ENABLE_API=true
AI_LAB_API_AUTH_ENABLED=true
AI_LAB_API_TOKEN=<non-empty local secret>
bind=127.0.0.1
```

`AI_LAB_SQLITE_DIR` 必须与 `AI_LAB_DATA_DIR` 一致归属；不得依赖 working directory
推导生产数据位置。启动输出或诊断入口必须安全展示最终生效的非敏感配置；token 与
Provider secret 只能显示“已配置/未配置”，不得回显值。

普通 Windows 用户从新 checkout 的可复现步骤必须包含：Python 3.11+、创建 venv、
安装 `.[local]`、建立显式 profile、启动 Uvicorn、调用 `/health` 与 `/health/ready`、
使用 Bearer token 访问业务 API，以及 Ctrl+C / 受控停止后的关闭确认。

配置错误必须转为稳定 `FailureInfo` 或明确的启动失败，不得自动选择其他数据目录、
关闭 auth、启用 mock 或忽略无效 timezone。

## Daily Review CLI

未来正式入口：

```powershell
python -m cli daily-review --date today
python -m cli daily-review --date yesterday
python -m cli daily-review --date today --json
```

要求：

- 直接从唯一 Composition Root 获得当前 container 的 `DailyReviewService`。
- 使用 service 的 `query_from_input()` 与 `get()`；不得复制日期、DST、分类、排序、
  去重或分页逻辑。
- 只接受 `today` / `yesterday`，默认分页继续使用 `limit=50 / offset=0`。
- human 与 JSON 输出映射同一份 `DailyReview`。
- 完整传递 `WorkspaceKey(tenant_id, workspace_id, namespace, session_id,
  agent_id, trace_id)`；不得永远硬编码 default workspace。
- 不调用 CEO Assistant、Provider 或 LLM，不发布事件，不产生任何写入。

## Deterministic Action Hint 数据合同

Action Hint 是纯只读 presentation contract。每条 hint 至少包含：

```text
source_type
source_id
status
reason_code
allowed_action
required_arguments
requires_revision
requires_confirmation
available_entrypoints
```

Hint 只能由 `source_type + status + reason_code + 当前真实领域合同` 确定。相同输入
必须产生相同顺序和内容。`available_entrypoints` 只列出当前真实存在并符合 Workspace、
revision、idempotency、confirmation 与 Saga 安全合同的入口。一个 `allowed_action`
至少存在一个真实、安全入口即可展示，不要求同时存在 API、CLI 和 CEO Assistant
三种入口；不存在任何真实安全入口时，必须省略该动作或返回稳定不可用说明。Action
Hint 不得把尚未存在的入口描述为可用入口。

Hint 不调用 LLM、不自动选择动作、不执行动作、不持久化、不创建 snapshot，也不改变
现有 Daily Review 分类和分页。Hint 与 Action Execution 严格分离。

### 当前真实动作矩阵

| 对象 | ID | READ | WRITE | API | CLI | CEO Assistant | revision / idempotency / confirm |
|---|---|---|---|---|---|---|---|
| UserTask | `ut_...` | list/get | create/update/complete/cancel | `/tasks` | `task` 当前经 CEO Assistant | create/read/update/complete/cancel | update 当前接受调用方 `expected_revision`；complete/cancel 当前不接受调用方 revision；无通用客户端 idempotency；模糊自然语言 fail closed |
| Reminder | `rem_...` | list/get/status/occurrences | create/reschedule/cancel | `/reminders` | `reminders`, `reminder-status`, `reminder-reschedule`, `reminder-cancel` | create/read/reschedule/cancel | reschedule 支持 expected revision；创建支持 idempotency key；写意图必须明确 |
| Waiting-For | `wf_...` | list/get/history | create/follow-up/snooze/resolve/cancel/reopen | `/waiting-for` | `waiting-for` | capture-confirm create，显式 ID lifecycle mutations | 所有 lifecycle mutation 要 expected revision；自然语言创建先 preview/capture 再按 Inbox ID confirm |
| Inbox | `inbox_...` | list/get | capture；resolve to UserTask/Reminder/Waiting-For/Work Log/Note；dismiss | `/inbox` | `inbox` | capture/read/confirm resolution | durable resolution claim/Saga 提供幂等与竞争恢复；Waiting-For resolution 要显式确认字段 |
| Work Log | `wl_...`（另有只读 legacy） | list/get | create only | `/work-logs` | `work-log` | create/list/get | create 可使用 idempotency；不存在 edit/complete/delete mutation |

UserTask revision 的当前事实与 SP-020 决策必须分开记录：

```text
UserTask update:
当前 Service 接受调用方 expected_revision；API PATCH 通过 revision 字段传入。

UserTask complete/cancel:
当前 Service 会读取最新对象，并使用读取时的 current.revision 执行 repository update；
当前 API 与 Service 均不接受调用方提供的 expected_revision。

SP-020 future implementation decision:
Review-to-Action 的 UserTask complete/cancel 必须增加显式 expected_revision，
防止用户依据旧 Daily Review 操作已经变化的对象。
```

以上 `complete/cancel expected_revision` 是未来 SP-020 产品实现范围，不是当前能力。
revision、idempotency、durable claim/Saga 与 confirmation 必须按动作分别声明，不得
套用一个统一 mutation 规则。

最终实现前必须用代码与测试再次核对每个 entrypoint。Hint 只可展示当前确实存在且符合
各动作真实安全合同的入口；不追求 API、CLI、CEO Assistant 矩阵对称。成功以
canonical SQLite 持久化对象、revision、resolution claim / Saga、confirmation 或
对应事件事实为依据，不以自然语言回复为依据。

## Review-to-Action 委托边界

Daily Review 继续只读。所有 mutation 委托现有：

```text
UserTaskService
ReminderManagementService / ReminderSchedulerBridge
WaitingForService
InboxService
WorkLogService
```

不得建立 Action 数据库、Review snapshot 数据库、第二套 Command Bus、第二套领域
mutation、Presenter 内写入、DailyReviewService 内写入或自动执行器。

统一原则：

```text
Read directly
Capture ambiguously
Confirm persistently
Mutate explicitly by canonical ID
```

## Workspace 合同

所有 READ、hint 与 WRITE 必须使用同一完整 `WorkspaceKey`。API 从受保护请求上下文
构造；CLI 必须提供显式参数或稳定 profile；CEO Assistant 必须透传 request 的
workspace。canonical ID 不能绕过 workspace ownership。跨 workspace 的同 ID、旧
数据别名或缺失 workspace evidence 必须按既有兼容合同处理或 fail closed，不能回退到
无过滤查询。

## FailureInfo 合同

- 配置、date、query、workspace、revision、state、auth、dependency、persistence 与
  lifecycle 失败必须使用现有 `FailureInfo` 分类。
- invalid input 必须在读取或 mutation 前失败。
- source failure 不得伪装成成功的部分 Daily Review。
- 模糊 action 不得降级为写入；应返回只读结果、明确 preview/confirm 或 validation。
- startup / readiness / shutdown / recovery 的 failure 必须保留 component、
  operation、trace_id、retryable 与安全 details。
- 不得在错误 details 或日志中泄露 token、API key 或 Provider secret。

## Scheduler、shutdown 与 restart recovery

Phase 0 必须先证明：

1. partial startup failure 能完成已初始化组件回滚；
2. 重复 shutdown 以及 container 内当前双 scheduler shutdown 调用是幂等的；
3. draining 后不接收新工作，已接受工作按 timeout/cancel 策略收敛；
4. EventBus 停止并且所有数据库连接在最后关闭；
5. shutdown failure 进入 `shutdown_failures` 与 FAILED lifecycle；
6. 新进程从同一目录恢复 scheduler jobs、过期 claims、reminder reconciliation、
   Inbox Saga 与 Waiting-For；
7. 不发生重复执行、丢失 job、对象状态漂移或旧数据静默遗弃。
8. 持续运行窗口必须覆盖多个 Scheduler tick、一次真实 one-shot job 执行、一个明确
   记录起止时间的空闲运行窗口、周期性 health 快照、background task 状态与
   `DatabaseManager.connection_count`；之后再执行优雅关闭、新进程重启和恢复验证。

若任一项无法证明，停止后续 CLI / hint / delegation 实现并报告 blocking finding。
一次瞬时启动和关闭不能作为持续运行验证通过的依据。

## 静止备份与隔离恢复

Local Daily Profile 的完整持久化集合为：

```text
<data_dir>/sqlite/episodic.db
<data_dir>/sqlite/semantic.db
<data_dir>/sqlite/decision.db
<data_dir>/sqlite/tasks.db                    (UserTask enabled)
<data_dir>/sqlite/inbox.db
<data_dir>/sqlite/followups.db
<data_dir>/sqlite/reminders.db                (Reminder enabled)
<data_dir>/sqlite/scheduler.db                (Scheduler enabled)
<data_dir>/sqlite/knowledge.db                (Knowledge enabled only)
<data_dir>/chroma/**                          (Knowledge/vector enabled only)
```

SQLite 运行期间还可能存在 `-wal` 与 `-shm` 文件；因此默认只承诺 Quiescent Backup：

```text
停止接收工作
→ 优雅关闭并确认 connection_count=0
→ 复制完整 data directory（不是挑选单个 .db）
→ 在不同的隔离目录恢复
→ 使用新进程、新 SystemContainer 和恢复目录启动
→ 执行对象、Review、Scheduler、Reminder、Inbox Saga 与 Waiting-For 一致性验证
```

当前 `DatabaseManager.backup()` / `restore()` 未实现。SP-020 不承诺运行中跨多个
SQLite 文件的一致快照；若需求必须依赖在线协调、跨库事务或 schema migration，立即
触发停止条件。

## 安全边界

- 只绑定 `127.0.0.1`；auth 显式开启并配置非空 token。
- 不新增 OAuth、JWT、RBAC、用户身份或强多租户声明。
- acceptance 使用 mock/test Provider，Provider call 数必须为 0。
- hint 永远不等同用户确认，不能执行外部行为或隐式 mutation。
- 备份可包含敏感业务数据，必须由用户选择受控本地路径；不自动上传。

## 替代方案

1. 继续使用 `/brief` 与 CEO Assistant：不能提供独立纯读 CLI，也不能固定日常 profile。
2. 在 Daily Review 内直接执行动作：破坏只读边界、确认合同和可审计性，拒绝。
3. 创建 Action / Snapshot 数据库：增加第二事实源与恢复复杂度，拒绝。
4. 在线复制各 SQLite 文件：无法默认保证跨库一致性，拒绝。
5. 先做 Web UI 或 Agent 自动规划：不解决本地持续运行与恢复，移出范围。

## 非目标

Recurring Reminder、外部通知、邮件/短信/企业微信/手机推送、Web UI、新
Project/Goal/Outcome 领域、Knowledge 主链路、Agent 自动规划或 Tool Calling、MCP
自动执行、用户身份、OAuth/JWT/RBAC、强多租户、任意历史日期 Review、Review
Snapshot、LLM 自动建议并执行、在线跨库一致快照、集群/高可用、复杂服务编排、大型
迁移、全仓重构、Plugin framework、Command Bus 重写和大规模 CEO Assistant 重构。

## 实施阶段

### Phase 0 — Product Entry and Lifecycle Gate

固定 Local Daily Profile、绝对数据目录、完整 WorkspaceKey、有效配置展示、health /
readiness / shutdown、scheduler 幂等与 restart recovery。只有门禁通过才进入 Phase 1。

### Phase 1 — Daily Review CLI

只建立直接调用现有 `DailyReviewService` 的 CLI。

### Phase 2 — Deterministic Action Hints

只建立纯 presentation Action Hint，不执行动作。

### Phase 3 — Review-to-Action Entrypoint Closure

只允许补齐 ACC-020 日常用户闭环实际需要的薄入口委托，不为入口对称性补齐所有领域
动作，不复制领域业务逻辑，不追求 API、CLI、CEO Assistant 的完整矩阵对称，也不新增
Work Log mutation。

### Phase 4 — Continuous Daily Acceptance

通过真实 Windows 进程、真实 SQLite、持续运行窗口、停止/重启、静止备份与隔离恢复
执行 ACC-020。

SP-020 产品实施需要一次明确的 Owner 授权。

Phase 0 是同一次 SP-020 实施授权内部的强制质量门禁，不需要在通过后再次获得 Owner
授权。Phase 0 失败、触发停止条件、需要改变已批准范围、需要拆分 Product SP，或需要
引入新的架构决策时，必须立即停止并重新请求 Owner 决策。

本 Planning Baseline 尚未授予这一次 SP-020 产品实施授权。

## 停止条件

出现以下任一情况立即停止并报告：

- main/Base 漂移或存在未处理 Product PR；
- 需要多个领域 schema、migration、Action/Review 数据库、Snapshot 或第二 Command Bus；
- 需要 LLM 选择对象/动作/写入内容；
- 需要绕过 WorkspaceKey、revision、idempotency 或 Inbox Saga；
- 需要新增 Work Log mutation或大规模 CEO Assistant 重构；
- scheduler restart 出现重复执行、丢 job、状态漂移，或 shutdown 幂等不能证明；
- 数据目录调整可能静默遗弃旧数据；
- 恢复必须依赖在线跨库一致快照；
- Windows 无法稳定启动、停止和恢复；
- 实际需要拆成两个以上独立 Product SP。

## 验收策略

ACC-020 使用真实 Windows subprocess、真实 Uvicorn、真实 SQLite 与隔离数据目录，
执行 profile、health/readiness、对象创建、Agenda、today/yesterday Review、hint、
canonical-ID mutation、Review 更新、workspace isolation、零 LLM、零未确认副作用、
EventBus、Scheduler、优雅关闭、新进程重启、静止备份与隔离恢复。所有场景在执行前
均为 `PLANNING_BASELINE / NOT_EXECUTED`。

## 版本与 Release 边界

本规划不修改 `0.34.0`、Tag 或 GitHub Release。SP-016 至 SP-020 的目标版本仍可记录
为 `0.35.0`，但这不是版本发布授权。产品 Implementation、其实施 PR 的 Ready/Merge、
Tag 与 Release 都需要后续独立授权。

## 治理状态

```text
SP-020 Planning Baseline:
APPROVED / MERGED / RECONCILED

SP-020 Implementation:
NOT APPROVED / NOT STARTED

ACC-020:
PLANNING_BASELINE / NOT_EXECUTED
```

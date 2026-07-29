# RFC-028：每日复盘读取模型与确定性跟进视图

Status: Adopted
Date: 2026-07-26
Target: SP-019
Implementation: MERGED / POST_MERGE_VERIFIED / ACCEPTED

## 1. 当前状态审计（Current State Audit）

本 RFC 以 `main@4e0d730a8bfdefa6277c7526a028e7247d7ddc43` 的真实代码为审计基线。

- `DailyAgendaService` 已是正式只读聚合器，直接读取 UserTask、ReminderInbox、WorkLog 与 Waiting-For；它回答“接下来要处理什么”，不是 Daily Review 的数据源。
- CEO Assistant 的 `_handle_brief()` 仍是旧式内部 handler。它用进程本地日期，直接读取最多 50 条 active UserTask、最多 5 条 Work Log，并从 Decision Memory 汇总最近决策；没有完整 Workspace 隔离、review date/as-of 分离、source status、reason code 或可回查输出。
- Work Log 已有 canonical `WorkLogService`，支持完整 `WorkspaceKey`、日期范围、稳定分页与 canonical/兼容 ID。
- Waiting-For 已有 canonical `WaitingForService`、完整 Workspace 边界及 follow-up history。
- Reminder 已有 `ReminderInboxService`，但仅在 Reminder、Scheduler 与 UserTask 均启用并组合时可用。
- Inbox 已有 `InboxService.list()`，Repository 在分页前按完整 Workspace 三元组过滤 pending item。
- UserTask 的创建入口会把完整 Workspace 三元组写入 `metadata.workspace`，现有 `user_tasks` 表也持久化 `metadata` JSON；但 `UserTaskService.get/list()` 与 Repository query 没有正式 `WorkspaceKey` 参数。`DailyAgendaService` 当前先跨 Workspace 读取并 `LIMIT 200`，再在 Python 中只比较 `workspace_id`，因此不能作为 SP-019 的安全查询边界。
- 当前数据结构足以通过 SQLite JSON predicate 在排序、分页与 limit 前下推完整 Workspace 过滤，也已有 `completed_at`、`cancelled_at`、`due_at`、`status` 列。无需新 Schema、Migration、第二张 UserTask 表或大规模 domain 重构。
- `core/system/factory.py` 中 Work Log、Waiting-For 与 Inbox 总是组合；UserTask 可禁用；ReminderInbox 取决于 Reminder 与 Scheduler 配置。Daily Review 必须如实呈现这些差异。

## 2. 用户问题（User Problem）

用户在一天结束或第二天开始工作时，需要快速知道指定本地日历日发生了什么、哪些事项已完成/仍在进行/被阻塞，以及生成时仍有哪些有明确原因的待跟进事项。

SP-019 的正式名称为：

```text
SP-019 — Daily Review Read Model & Deterministic Follow-up View
```

它不是智能助理、主动执行器、历史快照系统，也不是“大而全 Brief”。

## 3. Daily Agenda 边界（Daily Agenda Boundary）

```text
Daily Agenda:
接下来需要处理什么。

Daily Review:
指定本地日历日发生了什么，以及截至 as_of 仍未闭环的事项。

Deterministic Follow-up View:
依据显式状态与时间规则，解释哪些 canonical 对象需要关注。
```

`DailyReviewService` 直接读取 canonical services。禁止形成：

```text
Daily Review -> Daily Agenda -> canonical services
```

两者可复用纯时间窗口、稳定排序或基础输出类型，但 Daily Agenda API、CLI 与自然语言入口保持不变。

## 4. 现有 Daily Brief 替换（Existing Daily Brief Replacement）

现有 `brief`、`每日简报`、`今日总结` 等 deterministic READ intent 最终统一委托 `DailyReviewService`。

`_handle_brief()` 可保留兼容方法名，但内部不得继续独立读取 UserTask、Work Log 或 Decision Memory，不得保留第二套分类、排序和失败语义。旧 Daily Brief 的 Decision Memory 汇总不进入首版。

现有 `/brief` 与 CLI `brief` 仅作为历史兼容入口讨论：若实施阶段保留，它们只能委托同一 Service 与 presenter；它们不是 SP-019 新公共合同，也不得扩大首版入口范围。

## 5. Canonical 数据源（Canonical Sources）

Daily Review 只能直接读取：

1. `WorkLogService`
2. `WaitingForService`
3. `ReminderInboxService`
4. `InboxService`
5. `UserTaskService`

禁止扫描通用 `MemoryManager`、把 Daily Agenda 当作数据源、直接读数据库绕过 Service、用 LLM 选择事实，或用标题/文本相似度猜测关联。

## 6. UserTask Workspace 前置条件（UserTask Workspace Prerequisite）

SP-019 内部 Phase 0 定义窄范围的 **UserTask Workspace Query Closure**，它必须先完成，Daily Review 聚合才能开始：

- `UserTaskService.get/list()` 与 Repository protocol 显式接受完整 `WorkspaceKey`。
- `tenant_id + workspace_id + namespace` 全部参与 get/list 隔离。
- Repository 在排序、分页和 limit 之前用现有 `metadata.workspace` JSON 下推 Workspace predicate。
- 缺少完整 Workspace metadata 的 legacy task 仅归属于 `default/default/default`，不得按当前请求补齐或写回。
- query 增加 `completed_from/completed_to`、`cancelled_from/cancelled_to` 的半开区间过滤。
- 保留并验证 active、overdue 与 due range 查询；任何 `now` 依赖改用注入 Clock 或由 Service 显式传入 as-of。
- API/Agenda 等既有调用者随后传完整 WorkspaceKey；不得继续“跨 Workspace 读取 -> LIMIT -> Python metadata 过滤”。

审计结论：现有列和 metadata JSON 可以安全完成该闭环，不需要 Schema/Migration 或大规模 UserTask 重构。因此它保留为 SP-019 Phase 0，而不是独立前置 SP。若实施时发现必须新增 Schema、Migration 或第二套存储，立即停止并改为 `SPLIT_REQUIRED`，SP-019 标记 `BLOCKED_BY_USER_TASK_WORKSPACE_CLOSURE`。

Phase 0 已由 PR #50 合并并通过 post-merge Quality Gate，随后经 Owner 接受。Daily Review 实施以该 accepted Phase 0 为授权基线。

## 7. 日期与截至时点合同（Date and As-of Contract）

首版只接受：

```text
review_date = today | yesterday
```

使用系统配置的合法 IANA timezone 和注入 `Clock`：

- `generated_at`：Service 生成结果的 UTC instant。
- `as_of`：本次分类 Follow-up 的 UTC instant；首版等于本次调用读取的注入 Clock instant。
- `review_date`：按系统 timezone 解释的本地日历日期。
- `period_start`：该日期本地午夜转 UTC。
- `period_end`：下一本地日期午夜转 UTC。
- 事实窗口统一为 `[period_start, period_end)`。
- Follow-up 的当前状态与时间判断统一使用 `as_of`。

必须覆盖跨午夜、UTC 转换、23 小时 spring-forward 日与 25 小时 fall-back 日。禁止用 `timedelta(hours=24)` 推导本地下一午夜。

首版不接受任意 historical date。部分 canonical domain 只保存当前快照，无法可靠重建任意历史日期结束时的完整状态；SP-019 不得伪装成历史快照系统。`yesterday` 只报告可由 persisted timestamps 证明的昨日事实，并用当前 `as_of` 计算未闭环 Follow-up。

## 8. 输出模型（Output Model）

结构化结果至少包含：

```text
DailyReview
- workspace
- review_date
- timezone
- period_start
- period_end
- generated_at
- as_of
- source_status
- page
- completed
- in_progress
- blocked
- informational
- follow_ups
- pending_inbox
```

查询合同固定为：

```text
DailyReviewQuery
- review_date: today | yesterday
- limit: int = 50
- offset: int = 0
```

合法范围保持为 `limit: 1..100`、`offset: >= 0`。默认值属于 `DailyReviewQuery` 合同本身；API 与 CEO Assistant 必须构造同一个默认 `DailyReviewQuery(review_date, limit=50, offset=0)`，不得在各自入口设置不同默认值。

查询验证必须先于任何 canonical source 读取。`limit=0`、`limit=101` 或 `offset=-1` 均返回 `daily_review.query_invalid + ErrorCategory.VALIDATION`，且不得访问任何 canonical source。

`DailyReview.page` 是整份 Review 唯一的全局分页元数据：

```text
page
- count
- total_count
- limit
- offset
- has_more
```

- `count`：当前 page 的全局 item 数量。
- `total_count`：完成分类、canonical identity 去重与全局排序后的完整结果总数。
- `has_more`：`offset + count < total_count`。
- `offset >= total_count` 时返回空 page：`count=0`、`has_more=false`，所有 section items 为空。

六个 section 不拥有独立 offset、cursor、limit 或 `has_more`。每个 section 可同时返回：

```text
section_total_count
page_item_count
items
```

- `section_total_count`：该 section 在完整未分页结果中的总数。
- `page_item_count`：当前全局 page 中被分组到该 section 的 item 数量，必须等于 `items` 长度。

禁止继续使用语义不明的 section `count`，也不得先按 source 或 section 截断后再聚合。

每条 `DailyReviewItem` 至少包含：

```text
source_type
source_id
title
status
reason_code
effective_at
relevant_time_fields
```

`source_id` 只能是 `ut_...`、`rem_...`、`wf_...`、`wl_...`、`wl_legacy_...` 或 `inbox_...`。禁止输出无法回查来源的模糊总结。

## 9. 分类规则（Classification Rules）

日期事实只在相关事实时间位于 `[period_start, period_end)` 时进入相应 section：

| 来源事实 | 分区 | reason_code | effective_at |
|---|---|---|---|
| Work Log `completed` | completed | `work_log.completed` | `occurred_at` |
| Work Log `in_progress` | in_progress | `work_log.in_progress` | `occurred_at` |
| Work Log `blocked` | blocked | `work_log.blocked` | `occurred_at` |
| Work Log `informational` | informational | `work_log.informational` | `occurred_at` |
| UserTask `completed_at` in period | completed | `user_task.completed` | `completed_at` |
| UserTask `cancelled_at` in period | informational | `user_task.cancelled` | `cancelled_at` |
| Reminder `triggered_at` in period | completed | `reminder.triggered` | `triggered_at` |
| Waiting-For `resolved_at` in period | completed | `waiting_for.resolved` | `resolved_at` |
| Waiting-For `cancelled_at` in period | informational | `waiting_for.cancelled` | `cancelled_at` |

当前状态不能反向伪造历史事实。只有可持久化时间字段证明发生在 review period 的 terminal transition 才进入日期事实 section。

### 当前未闭环 Inbox（Current Pending Inbox）

`pending_inbox` 是截至 `as_of` 的当前未闭环视图，不受 `review_date` 的 `[period_start, period_end)` 日期事实窗口过滤。只要 Inbox item 在 `as_of` 时仍为 pending，无论 `created_at` 属于 today、yesterday 或更早日期，都必须进入 `pending_inbox` 候选；不得用 `created_at` 排除较早创建但仍 pending 的 Inbox item。

```text
reason_code=inbox.pending
section=pending_inbox
effective_at=created_at
predicate=status pending at as_of
```

`created_at` 只用于 `effective_at`、全局稳定排序与 `relevant_time_fields`。同一个 Inbox item 只进入 `pending_inbox`，不得同时复制到 `follow_ups`，也不得作为 `review_date` 日期事实。完成唯一 section 选择后，这些当前 pending Inbox items 必须计入全局 `total_count` 与 `pending_inbox.section_total_count`，并参与同一套全局分页。

## 10. Follow-up 原因码（Follow-up Reason Codes）

首版只允许以下候选：

| reason_code | 确定性谓词 | 严重程度 |
|---|---|---:|
| `user_task.overdue` | active 且 `due_at < as_of` | 10 |
| `user_task.due_soon` | active 且 `as_of <= due_at < as_of + 24h` | 40 |
| `waiting_for.review_due` | open 且 `next_review_at <= as_of` | 20 |
| `waiting_for.expected_overdue` | open 且 `expected_by < as_of` | 10 |
| `reminder.failed` | current ReminderInbox status failed | 10 |
| `reminder.retrying` | current ReminderInbox status retrying | 20 |
| `reminder.due_soon` | scheduled/retrying 且 `as_of <= scheduled_for < as_of + 24h` | 40 |
| `inbox.pending` | Inbox status pending at `as_of` | 50 |

`due_soon` 窗口固定为 `[as_of, as_of + 24 hours)`。不使用 AI 紧急度、importance、不可解释分数或 LLM。

一个对象命中多个原因时保留 severity 数值最小的最高严重度原因；同 severity 按 reason code 升序稳定决胜。

## 11. 排序与去重（Sorting and Deduplication）

全局稳定顺序：

```text
section priority
-> reason severity
-> effective_at
-> source priority
-> canonical source_id
```

section priority 固定为：

```text
blocked
follow_ups
in_progress
completed
informational
pending_inbox
```

source priority 固定为：

```text
work_log
user_task
waiting_for
reminder
inbox
```

同一 section 内 `effective_at` 升序；缺失时间排在有时间之后，最终以 `(source_type, source_id)` 决胜。去重 identity 只能是 `(source_type, source_id)`，不能按标题、联系人、正文相似度或 LLM。

同一 canonical 对象在一份报告中只能进入一个最高优先级 section。例如 blocked Work Log 只进 blocked；overdue UserTask 只进 follow_ups。`pending_inbox` 不是对 `inbox.pending` 的第二份复制，而是该 reason 的唯一展示 section。

全局分页处理顺序固定为：

```text
读取全部 canonical source 候选
-> deterministic classification
-> 按 (source_type, source_id) 去重并选定唯一 section
-> 按全局稳定排序键排序
-> 计算 total_count 与各 section_total_count
-> 对全局结果应用 offset / limit
-> 将当前 page items 按 section 分组
-> 计算 page.count、has_more 与各 page_item_count
```

不得先对单个 source 或 section 应用业务截断。source service 的内部读取可以分页，但 `DailyReviewService` 必须遍历其可见结果，直到取得完整候选或明确失败；不得让上游 page size 成为 Daily Review 的静默 candidate cap。

## 12. 数据源可用性（Source Availability）

成功返回的 `DailyReview.source_status` 对每个 canonical source 只能记录：

```text
available
disabled
not_configured
```

- `available`：已启用且查询成功，包括合法空集合。
- `disabled`：配置明确关闭。
- `not_configured`：运行时没有所需 service/dependency。

`disabled/not_configured` 不阻止其余来源生成 Review，但必须在 `source_status` 显式暴露缺口，不能伪装成“没有事项”。

`failed` 只允许作为 source evaluation 的内部瞬时结果：已启用来源的查询、投影或完整性验证失败后，Service 立即转为 `daily_review.source_failed`，不返回 `DailyReview` payload。因此成功 payload 的 `source_status` 永远不包含 `failed`。

## 13. 失败语义（Failure Semantics）

已启用来源发生 runtime error、数据完整性错误或 legacy projection failure 时，整份 Review fail closed，不返回看似完整的部分成功结果。

| 代码 | 类别 | 含义 |
|---|---|---|
| `daily_review.unavailable` | DISABLED | 配置显式关闭 DailyReviewService |
| `daily_review.unavailable` | NOT_CONFIGURED | Composition Root 未组合所需 DailyReviewService |
| `daily_review.query_invalid` | VALIDATION | query、limit 或 offset 合同无效 |
| `daily_review.date_invalid` | VALIDATION | 非 today/yesterday 或日期无法解释 |
| `daily_review.timezone_invalid` | VALIDATION | 系统 timezone 非合法 IANA timezone |
| `daily_review.source_failed` | DEPENDENCY_FAILURE | 已启用 canonical source 查询或投影失败 |
| `daily_review.workspace_invalid` | VALIDATION | Workspace 三元组缺失或无效 |

`DailyReviewQuery` 必须在 source evaluation 前完成验证。`limit=0`、`limit=101` 与 `offset=-1` 均返回 `daily_review.query_invalid + ErrorCategory.VALIDATION`；该失败路径不得读取任何 canonical source，也不得返回部分 `DailyReview` payload。

所有失败使用 `FailureInfo(component="daily_review", operation="get")`。`daily_review.source_failed.details` 只允许 `source`、`upstream_code`、`upstream_category`；不得泄露数据库路径、原始异常、正文、内部 SQL 或 traceback。

配置关闭与未组合必须分别保留 `ErrorCategory.DISABLED` 和 `ErrorCategory.NOT_CONFIGURED`，不得把单个 FailureInfo category 写成复合值 `DISABLED / NOT_CONFIGURED`。

## 14. Workspace 合同（Workspace Contract）

所有来源接收同一个 canonical `WorkspaceKey`，并严格比较：

```text
tenant_id
workspace_id
namespace
```

API 从现有安全中间件与 Workspace headers 构造 WorkspaceKey；CEO Assistant 使用 `ApplicationRequest.workspace_key`。过滤必须在候选选择、分页、排序和 limit 前生效。trace/session 不是隔离键。

## 15. 入口（Entry Points）

首版规划只批准：

```text
DailyReviewService
CEO Assistant deterministic READ intent
GET /daily-review?date=today
GET /daily-review?date=yesterday
GET /daily-review?date=today&limit=50&offset=0
GET /daily-review?date=yesterday&limit=50&offset=0
```

以下请求必须分别构造完全相同的 `DailyReviewQuery` 并返回相同结果：

```text
GET /daily-review?date=today
== GET /daily-review?date=today&limit=50&offset=0

GET /daily-review?date=yesterday
== GET /daily-review?date=yesterday&limit=50&offset=0
```

API query parameter `date` 映射到 `DailyReviewQuery.review_date`；省略分页参数时使用 `limit=50`、`offset=0`。CEO Assistant deterministic READ intent 在用户没有提供结构化分页参数时同样使用 `limit=50`、`offset=0`。API 与 CEO Assistant 必须构造同一个默认 `DailyReviewQuery`，不得各自设置不同默认值，并共享同一 Service、模型、全局分页、reason code、排序与 FailureInfo presenter。CLI 新入口延期。Daily Agenda 的所有入口不变。

## 16. 存储决策（Storage Decision）

Daily Review 是按需、非持久化 read model，不是新 canonical domain：

- 无 DailyReview 数据库或表；
- 无持久化 Review snapshot；
- 无 migration 或 write-back；
- 不直接查询数据库绕过 source service。

## 17. LLM 边界（LLM Boundary）

事实选择、分类、Follow-up、去重、排序、来源可用性和失败语义全部 deterministic。首版无 Provider 依赖、无 LLM 调用。自然语言 presenter 只能格式化结构化结果，不能改变事实或 reason code。

## 18. 副作用边界（Side-effect Boundary）

Daily Review 查询必须证明：

- 数据库行数不变；
- 对象 revision 不变；
- event 集合不变；
- Inbox 状态不变；
- Waiting-For history 不变；
- Provider 调用次数为零。

禁止新 Event type、EventBus publish、任务/Reminder 创建、Waiting-For mutation、Inbox resolution、主动推送、Scheduler 或定时生成。

## 19. 被拒绝的替代方案（Alternatives Considered）

### A. 复用 Daily Agenda 输出

拒绝。Agenda 语义与窗口不同，且会形成二次聚合、丢失 source availability 与日期事实。

### B. 扩大旧 `_handle_brief()`

拒绝。会保留第二套聚合器、进程本地时间、Decision Memory 与不完整 Workspace 边界。

### C. 扫描 MemoryManager

拒绝。它不是 Work Log/Task/Follow-up 的产品真相边界，也会重新引入 candidate cap 与模糊投影。

### D. 持久化 Daily Review

拒绝。首版不需要 snapshot、event 或新 Schema；持久化会伪装历史重建能力。

### E. 用 LLM 生成 Follow-up

拒绝。不可测试、不可解释且可能产生副作用或虚构关联。

### F. 独立 UserTask 前置 SP

当前不选择。真实审计证明现有 metadata JSON 与时间列足以做窄闭环；若实施证据推翻此结论，则立即拆分。

## 20. 实施阶段（Implementation Phases）

以下顺序已用于已合并的 SP-019 实施：

0. UserTask Workspace Query Closure：完整 Workspace 下推、terminal ranges、as-of query。
1. `DailyReviewQuery`、`DailyReview`、全局 page metadata、时间边界、FailureInfo 与 source adapter。
2. deterministic classification、follow-up、canonical identity 去重、全局稳定排序、`total_count` 后应用 `offset/limit`，再按 section 分组并计算 `section_total_count/page_item_count`。
3. Composition Root 与旧 brief 单一委托切换。
4. CEO Assistant READ intent 与 `GET /daily-review`。
5. ACC-019 自动化、真实进程验收与零副作用证据。

Phase 0 已接受；Phase 1～4 已完成。Phase 5 的正式 ACC-019 A～M 已在 Approved Implementation Head `1f2975503cd79047137a4a9f47096668fd4341c5` 上通过，状态为 `PASSED / FINAL`。

## 21. 非目标（Non-goals）

- 任意历史日期或历史趋势；
- Daily Agenda 改版；
- Decision Memory、Knowledge 或通用 Memory 汇总；
- CLI 新入口；
- 主动推送、Scheduler、自动写入或自动执行；
- Review 保存、分享、导出或通知；
- LLM 总结、优先级评分、相似度关联；
- UserTask Schema/Migration 或大规模重构；
- 产品版本、Tag、Release 或发布授权变更。

## 22. 风险（Risks）

- UserTask legacy metadata 不完整导致错误归属；
- current snapshot 被误当作历史 end-of-day 状态；
- optional source 空集合与不可用被混淆；
- 多来源 pagination 静默丢项；
- 同一对象跨 section 重复；
- DST 窗口按固定 24 小时计算；
- 旧 Brief 与新 Review 并存导致事实漂移。

通过 fail-closed Workspace、显式 source status、半开窗口、canonical identity、有界 page、单一 Service 与 ACC-019 控制。

## 23. 停止条件（Stop Conditions）

出现下列任一情况立即停止相应扩大动作并报告 `BLOCKER`、`SPLIT_REQUIRED` 或 `DEFERRED`：

- UserTask Workspace Closure 需要新 Schema、Migration、第二套表或大规模重构；
- 必须依赖 LLM 才能定义事实或 Follow-up；
- 必须持久化 Review 才能完成首版；
- 必须修改 Daily Agenda 才能实现 Review；
- 需要主动推送、Scheduler 或自动写入；
- acceptance 开始扩张为任意历史状态重建；
- 最新 main 已存在冲突的 SP-019 branch、PR 或 Planning Baseline。

## 24. 治理状态（Governance）

本 RFC 已在 Approved Implementation Head `1f2975503cd79047137a4a9f47096668fd4341c5` 实现；ACC-019 A～M 为 `PASSED / FINAL`。Feature PR #51 已 Squash merged as `a3abf5f5f9a1e5efb7296d7381e5c44c70c4cd49`，Main Quality Gate `30382312419` PASSED。

```text
SP-019 Planning Baseline: APPROVED / MERGED / RECONCILED
SP-019 Implementation: APPROVED / MERGED / POST_MERGE_VERIFIED
SP-019 Phase 0: APPROVED / MERGED / POST_MERGE_VERIFIED / ACCEPTED
Daily Review: MERGED / POST_MERGE_VERIFIED / ACCEPTED
ACC-019: PASSED / FINAL
```

RFC-028 已 Adopted；该状态不表示 Release Final，也不改变产品版本、Tag 或 Release。

# SP-019 — Daily Review Read Model & Deterministic Follow-up View 验收规划

状态：PLANNING_BASELINE / NOT_EXECUTED

规划日期：2026-07-26（Asia/Shanghai）

Planning PR：#48（MERGED）

Approved Planning Head：`282dd939ff264b0f23d5070b6f632aa0442531ea`

Planning Merge Commit：`e7fc5b1dd66ff7828c1697bfd5610f300599eee5`

Planning Merged At：`2026-07-26T14:19:41Z`

Post-Planning main Quality Gate：`30205853257`（SUCCESS）

Independent Planning Review：APPROVED

目标开发线：v0.35.0

当前源码版本：`0.34.0`

RFC：RFC-028 — Proposed / Planning Baseline

ADR：ADR-061、ADR-062 — Proposed / Planning Baseline

Owner approval：GRANTED

Phase 0：ACCEPTED

Implementation：IMPLEMENTED ON DRAFT / PENDING REVIEW

> 本文定义正式验收目录与证据要求。Daily Review 已在实施 Draft 完成自动化覆盖，但本轮没有执行正式 ACC-019，A～M 仍全部为 NOT_EXECUTED。

## 启动门禁

执行 ACC-019 前必须同时满足：

1. SP-019 Planning PR 已独立审查并合并；
2. 最新 main Quality Gate 成功；
3. Owner 明确批准 SP-019 Implementation；
4. 实施分支从届时最新 main 创建；
5. UserTask Workspace Query Closure Phase 0 已完成且不需要 Schema/Migration；
6. Approved Head 已固定；
7. 隔离数据目录、真实 API/CEO Assistant 入口与零 Provider 凭据已准备。

Planning PR 合并本身不批准实施。

## 通用证据要求

每个场景必须记录：

- Approved Head 与执行入口；
- 完整 WorkspaceKey；
- 注入 Clock、系统 IANA timezone、review date、period 与 as-of；
- source status、canonical source ID、reason code 与 relevant time fields；
- page.count、total_count、limit、offset、has_more、section_total_count、page_item_count、稳定顺序与去重结果；
- 查询前后数据库行数、revision、event、Inbox 状态与 Waiting-For history；
- Provider 调用次数；
- 完整安全 FailureInfo；
- 对应自动化测试名和真实结果。

无效命令、编码、driver 或 harness 问题单列为 `INVALID_ACCEPTANCE_HARNESS`，不得计作产品通过或失败。

## 场景目录

| 场景 | 目标 | 当前状态 |
|---|---|---|
| A — 基线与现有 Brief 替换 | 只有一个 Daily Review 聚合边界；旧 brief 只委托同一 Service | NOT_EXECUTED |
| B — Workspace 隔离 | 五个来源完整三元组隔离，过滤先于排序、分页与 limit | NOT_EXECUTED |
| C — 本地日期与 DST | today/yesterday、跨午夜、UTC 转换、23/25 小时日 | NOT_EXECUTED |
| D — Review Date 与 As-of 分离 | 日期事实窗口与当前 Follow-up 状态严格分离 | NOT_EXECUTED |
| E — 多数据源聚合 | canonical sources 的确定性映射和正式 source ID | NOT_EXECUTED |
| F — Disabled 与 Not Configured | 缺口显式可见，其余来源仍可生成 | NOT_EXECUTED |
| G — 已启用数据源失败 | runtime、完整性、legacy projection failure 整体 fail closed | NOT_EXECUTED |
| H — 事实分类 | completed/in_progress/blocked/informational 映射 | NOT_EXECUTED |
| I — 确定性 Follow-up | 全部允许 reason code、severity 与固定 24h 窗口 | NOT_EXECUTED |
| J — 排序、去重与可追溯性 | 稳定顺序、单实体单 section、canonical identity | NOT_EXECUTED |
| K — 全局分页与截断 | 全局 limit/offset、total_count、has_more、跨页无遗漏 | NOT_EXECUTED |
| L — CEO Assistant 与 API 一致性 | 相同 query 下的 facts、ID、reason、分页、排序与 FailureInfo | NOT_EXECUTED |
| M — 零副作用与重启 | 零写入、零 event、零 Provider，重启后一致 | NOT_EXECUTED |

## ACC-019-A — 基线与现有 Brief 替换

验证 `DailyReviewService` 是唯一聚合器。CEO Assistant 的 `brief`、`每日简报`、`今日总结` 等 READ intent 以及保留的兼容 handler/route 如存在，都必须委托同一 Service；不得直接读取 UserTask、Work Log、Decision Memory 或维护第二套排序。Decision Memory 不出现在结果。

状态：NOT_EXECUTED

## ACC-019-B — Workspace 隔离

在相同 workspace_id、不同 tenant/namespace 等组合中注入数据。验证五个 source 只返回完整三元组匹配对象，UserTask get/list 的 Workspace predicate 在排序、分页、limit 前生效；legacy 缺失 Workspace 的 UserTask 只属于 default/default/default。

状态：NOT_EXECUTED

## ACC-019-C — 本地日期与 DST

冻结 Clock 并覆盖 today/yesterday、本地午夜边界、UTC 转换、跨午夜事项、America/New_York spring-forward 23 小时日与 fall-back 25 小时日。窗口必须是相邻本地午夜转换的 `[start,end)`。

状态：NOT_EXECUTED

## ACC-019-D — Review Date 与 As-of 分离

验证 `review_date` 只决定日期事实窗口，`as_of` 只决定当前未闭环视图。yesterday 不得把当前 snapshot 伪装成昨日结束时 snapshot，当前 overdue/retrying 可以作为截至 as-of 的 Follow-up，但必须保留真实时间字段。创建时间早于 review period、但在 `as_of` 时仍为 pending 的 Inbox item 必须出现在 `pending_inbox`，证明 `review_date` 与 `as_of` 没有混用。

状态：NOT_EXECUTED

## ACC-019-E — 多数据源聚合

分别注入 Work Log、UserTask、Reminder、Waiting-For 与 Inbox 对象，验证只通过 canonical services 读取、ID 可回查、source type 正确、无 Daily Agenda/MemoryManager/数据库直读。

状态：NOT_EXECUTED

## ACC-019-F — Disabled 与 Not Configured

逐一关闭或不组合 optional source，验证成功 payload 的 `source_status` 只出现 `available/disabled/not_configured`，其余来源仍可生成 Review；合法空集合必须是 `available`，不能与缺失混淆。分别验证 DailyReviewService 显式关闭返回 `daily_review.unavailable + ErrorCategory.DISABLED`，Composition Root 未组合返回 `daily_review.unavailable + ErrorCategory.NOT_CONFIGURED`。

状态：NOT_EXECUTED

## ACC-019-G — 已启用数据源失败

对每个已启用 source 注入 runtime error、数据完整性错误与可适用的 legacy projection failure。`failed` 只能是内部 source evaluation 结果；整份 Review 必须返回 `daily_review.source_failed`，不得返回 `DailyReview` payload 或把 `failed` 放进成功 `source_status`；details 只含 source/upstream_code/upstream_category。

状态：NOT_EXECUTED

## ACC-019-H — 事实分类

覆盖：

- `work_log.completed/in_progress/blocked/informational`
- `user_task.completed/cancelled`
- `reminder.triggered`
- `waiting_for.resolved/cancelled`

验证时间落入半开 period、section、reason_code、effective_at 和 relevant time fields。日期事实分类不得包含 Inbox pending；`inbox.pending` 是由 `as_of` 控制的当前未闭环视图，不得作为 `review_date` 日期事实。

状态：NOT_EXECUTED

## ACC-019-I — 确定性 Follow-up

逐一覆盖：

```text
user_task.overdue
user_task.due_soon
waiting_for.review_due
waiting_for.expected_overdue
reminder.failed
reminder.retrying
reminder.due_soon
inbox.pending
```

验证 due_soon 为 `[as_of, as_of + 24 hours)`，边界 instant、severity 决胜与无 LLM/importance 评分。`inbox.pending` 必须由 Inbox item 在 `as_of` 的当前 pending 状态决定，不由 `review_date` 决定；较早创建但仍 pending 的 item 不得被 review period 排除。

状态：NOT_EXECUTED

## ACC-019-J — 排序、去重与可追溯性

构造相同时间、多个 reason 与重复来源，验证 section priority、reason severity、effective time、source priority、canonical ID 的稳定顺序；去重只按 `(source_type, source_id)`，每个对象只进入最高优先级 section。同一个 Inbox item 只进入 `pending_inbox`，不得重复进入 `follow_ups`。

状态：NOT_EXECUTED

## ACC-019-K — 全局分页与截断

使用 `DailyReviewQuery(review_date, limit=50, offset=0)` 构造跨多个 source 与 section、总数超过 limit 的结果。验证处理顺序严格为“完整 canonical source 读取 -> 分类 -> canonical identity 去重 -> 全局稳定排序 -> total_count -> offset/limit -> 当前 page 按 section 分组”。

覆盖默认 `limit=50/offset=0`、`limit=1`、`limit=100`、非法 `limit=0/101`、非法 `offset=-1`、中间页、最后一页以及 `offset >= total_count` 空页。验证：

- 省略 `limit/offset` 与显式 `limit=50/offset=0` 构造完全相同的 `DailyReviewQuery`；
- `limit=0`、`limit=101`、`offset=-1` 返回 `daily_review.query_invalid + ErrorCategory.VALIDATION`，且不得访问任何 canonical source；
- `page.count`、`total_count`、`limit`、`offset`、`has_more` 精确；
- 跨页顺序稳定，无重复、无遗漏；
- 每个 section 的 `section_total_count` 是完整未分页结果中的数量；
- 当前 pending Inbox items 计入全局 `total_count` 与 `pending_inbox.section_total_count`，并参与同一套全局分页；
- `page_item_count` 等于当前 page 中该 section 的 items 长度；
- 不存在六套独立 section offset，也不先对 source/section 截断；
- offset 超出总数时所有 section items 为空、`page.count=0`、`has_more=false`。

禁止 candidate cap 或静默截断。

状态：NOT_EXECUTED

## ACC-019-L — CEO Assistant 与 API 一致性

对同一 Workspace、Clock 和 source snapshot 调用 CEO Assistant deterministic READ intent 与：

```text
GET /daily-review?date=today
GET /daily-review?date=today&limit=50&offset=0
GET /daily-review?date=yesterday
GET /daily-review?date=yesterday&limit=50&offset=0
```

验证 API 省略分页参数与显式 `limit=50/offset=0` 的结果一致。CEO Assistant 未提供结构化分页参数时必须使用同一个默认 `DailyReviewQuery(review_date, limit=50, offset=0)`；其默认第一页与 API 默认第一页必须返回相同当前 page 事实集合、canonical ID、reason、全局分页 metadata、section counts、排序、source status 和 FailureInfo。API Workspace 来自现有安全 headers。

状态：NOT_EXECUTED

## ACC-019-M — 零副作用与重启

在真实进程中查询前后比较数据库行数、revision、event 集合、Inbox 状态、Waiting-For history 和 Provider 计数；全部不变且 Provider 为零。重启后相同 Clock/数据得到相同结构化结果。不得产生 Review DB/table/snapshot、EventBus publish、migration、write-back、任务/Reminder/Waiting-For/Inbox mutation、主动推送或 Scheduler 行为。

状态：NOT_EXECUTED

## 当前治理结论

```text
SP-019 Planning Baseline: APPROVED / MERGED / RECONCILED
SP-019 Implementation: OWNER APPROVED
SP-019 Phase 0: ACCEPTED
Daily Review: IMPLEMENTED ON DRAFT / PENDING INDEPENDENT REVIEW
ACC-019: PLANNING_BASELINE / NOT_EXECUTED
```

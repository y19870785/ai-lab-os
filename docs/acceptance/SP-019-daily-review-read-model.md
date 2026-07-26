# SP-019 — Daily Review Read Model & Deterministic Follow-up View 验收规划

状态：PLANNING_BASELINE / NOT_EXECUTED

规划日期：2026-07-26（Asia/Shanghai）

目标开发线：v0.35.0

当前源码版本：`0.34.0`

RFC：RFC-028 — Proposed / Planning Baseline

ADR：ADR-061、ADR-062 — Proposed / Planning Baseline

Implementation：NOT APPROVED

Coding：NOT STARTED

> 本文只定义未来验收目录与证据要求。本轮没有执行 ACC-019，也不得把 Planning Baseline 描述为产品实现或验收通过。

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
- count、has_more、limit、稳定顺序与去重结果；
- 查询前后数据库行数、revision、event、Inbox 状态与 Waiting-For history；
- Provider 调用次数；
- 完整安全 FailureInfo；
- 对应自动化测试名和真实结果。

无效命令、编码、driver 或 harness 问题单列为 `INVALID_ACCEPTANCE_HARNESS`，不得计作产品通过或失败。

## 场景目录

| 场景 | 目标 | 当前状态 |
|---|---|---|
| A — Baseline and Existing Brief Replacement | 只有一个 Daily Review 聚合边界；旧 brief 只委托同一 Service | NOT_EXECUTED |
| B — Workspace Isolation | 五个来源完整三元组隔离，过滤先于排序、分页与 limit | NOT_EXECUTED |
| C — Local Date and DST | today/yesterday、跨午夜、UTC 转换、23/25 小时日 | NOT_EXECUTED |
| D — Review Date vs As-of | 日期事实窗口与当前 Follow-up 状态严格分离 | NOT_EXECUTED |
| E — Multi-source Aggregation | canonical sources 的确定性映射和正式 source ID | NOT_EXECUTED |
| F — Disabled and Not Configured | 缺口显式可见，其余来源仍可生成 | NOT_EXECUTED |
| G — Enabled-source Failure | runtime、完整性、legacy projection failure 整体 fail closed | NOT_EXECUTED |
| H — Fact Classification | completed/in_progress/blocked/informational 映射 | NOT_EXECUTED |
| I — Deterministic Follow-up | 全部允许 reason code、severity 与固定 24h 窗口 | NOT_EXECUTED |
| J — Sorting, Deduplication and Traceability | 稳定顺序、单实体单 section、canonical identity | NOT_EXECUTED |
| K — Pagination and Truncation | count、has_more、section limit、无静默遗漏 | NOT_EXECUTED |
| L — CEO Assistant and API Consistency | 相同 facts、ID、reason、排序与 FailureInfo | NOT_EXECUTED |
| M — Zero Side Effects and Restart | 零写入、零 event、零 Provider，重启后一致 | NOT_EXECUTED |

## ACC-019-A — Baseline and Existing Brief Replacement

验证 `DailyReviewService` 是唯一聚合器。CEO Assistant 的 `brief`、`每日简报`、`今日总结` 等 READ intent 以及保留的兼容 handler/route 如存在，都必须委托同一 Service；不得直接读取 UserTask、Work Log、Decision Memory 或维护第二套排序。Decision Memory 不出现在结果。

状态：NOT_EXECUTED

## ACC-019-B — Workspace Isolation

在相同 workspace_id、不同 tenant/namespace 等组合中注入数据。验证五个 source 只返回完整三元组匹配对象，UserTask get/list 的 Workspace predicate 在排序、分页、limit 前生效；legacy 缺失 Workspace 的 UserTask 只属于 default/default/default。

状态：NOT_EXECUTED

## ACC-019-C — Local Date and DST

冻结 Clock 并覆盖 today/yesterday、本地午夜边界、UTC 转换、跨午夜事项、America/New_York spring-forward 23 小时日与 fall-back 25 小时日。窗口必须是相邻本地午夜转换的 `[start,end)`。

状态：NOT_EXECUTED

## ACC-019-D — Review Date vs As-of

验证 `review_date` 只决定日期事实窗口，`as_of` 只决定当前 Follow-up。yesterday 不得把当前 snapshot 伪装成昨日结束时 snapshot，当前 overdue/retrying 可以作为截至 as-of 的 Follow-up，但必须保留真实时间字段。

状态：NOT_EXECUTED

## ACC-019-E — Multi-source Aggregation

分别注入 Work Log、UserTask、Reminder、Waiting-For 与 Inbox 对象，验证只通过 canonical services 读取、ID 可回查、source type 正确、无 Daily Agenda/MemoryManager/数据库直读。

状态：NOT_EXECUTED

## ACC-019-F — Disabled and Not Configured

逐一关闭或不组合 optional source，验证 `source_status=disabled/not_configured`，其余来源仍可生成 Review；合法空集合必须是 `available`，不能与缺失混淆。

状态：NOT_EXECUTED

## ACC-019-G — Enabled-source Failure

对每个已启用 source 注入 runtime error、数据完整性错误与可适用的 legacy projection failure。整份 Review 必须返回 `daily_review.source_failed`，不得带部分成功 payload；details 只含 source/upstream_code/upstream_category。

状态：NOT_EXECUTED

## ACC-019-H — Fact Classification

覆盖：

- `work_log.completed/in_progress/blocked/informational`
- `user_task.completed/cancelled`
- `reminder.triggered`
- `waiting_for.resolved/cancelled`

验证时间落入半开 period、section、reason_code、effective_at 和 relevant time fields。

状态：NOT_EXECUTED

## ACC-019-I — Deterministic Follow-up

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

验证 due_soon 为 `[as_of, as_of + 24 hours)`，边界 instant、severity 决胜与无 LLM/importance 评分。

状态：NOT_EXECUTED

## ACC-019-J — Sorting, Deduplication and Traceability

构造相同时间、多个 reason 与重复来源，验证 section priority、reason severity、effective time、source priority、canonical ID 的稳定顺序；去重只按 `(source_type, source_id)`，每个对象只进入最高优先级 section。

状态：NOT_EXECUTED

## ACC-019-K — Pagination and Truncation

每个 section 产生超过 limit 的结果，验证精确 count、has_more、limit、跨页无重复/遗漏、稳定排序。禁止 candidate cap 或静默截断。

状态：NOT_EXECUTED

## ACC-019-L — CEO Assistant and API Consistency

对同一 Workspace、Clock 和 source snapshot 调用 CEO Assistant deterministic READ intent 与：

```text
GET /daily-review?date=today
GET /daily-review?date=yesterday
```

验证相同事实集合、canonical ID、reason、排序、source status 和 FailureInfo。API Workspace 来自现有安全 headers。

状态：NOT_EXECUTED

## ACC-019-M — Zero Side Effects and Restart

在真实进程中查询前后比较数据库行数、revision、event 集合、Inbox 状态、Waiting-For history 和 Provider 计数；全部不变且 Provider 为零。重启后相同 Clock/数据得到相同结构化结果。不得产生 Review DB/table/snapshot、EventBus publish、migration、write-back、任务/Reminder/Waiting-For/Inbox mutation、主动推送或 Scheduler 行为。

状态：NOT_EXECUTED

## 当前治理结论

```text
SP-019 Planning Baseline: DEFINED
SP-019 Implementation: NOT APPROVED
Coding: NOT STARTED
ACC-019: PLANNING_BASELINE / NOT_EXECUTED
```

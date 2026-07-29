# RFC-023：Daily Agenda 读取模型

Status: Accepted

## 用户问题

用户需要统一查看今天的 Task、Reminder 与已完成 Work，而不必分别查询多个 Endpoint。

## 目标

- 将 Reminder、UserTask 与 Work Log 聚合为一个读取模型；
- 支持 `today`、`next`、`attention`、`completed` 和 `all` View；
- 支持 Workspace 隔离、timezone 与分页。

## 非目标

- 不新增权威来源或 Agenda Database；
- 不使用 LLM 分类 Agenda Intent；
- 不进行后台 Materialization。

## 关键决策

- `DailyAgendaService` 是唯一聚合边界；
- `ReminderInbox` 每次读取最多 100 个，分页 Adapter 可读取多页；
- 应用候选上限 1200 与 `offset`/`limit` 前，先对全部来源全局排序；
- 任一来源失败都返回带结构化 Detail 的 `agenda.query_failed`；
- 保留 SP-012 Reminder Query Expression，不产生语义漂移。

## 视图

- `today`：今天计划的非 cancelled Reminder、`due_at` 在今天窗口的 active Task、今天的
  Work Log；
- `next`：未来 N 小时内可行动的 Reminder 与 Task，默认 N=3；
- `attention`：failed/retrying Reminder 与 overdue Task；
- `completed`：今天窗口内的 triggered Reminder 与 Work Log；
- `all`：用于调试的完整聚合。

## 已知限制

- 跨来源分页不是数据库 Snapshot；
- Deep offset 可能增加成本；
- 没有基于 LLM 的 Intent Classification；
- 没有外部通知或 Web UI。

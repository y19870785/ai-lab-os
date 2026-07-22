# ADR-055 — Daily Agenda Optional-Source Aggregation

状态：Accepted

## 背景

Daily Agenda 是多个 canonical domain 的只读聚合视图。此前它只在 Reminder 与 Scheduler 链完整启用时创建，导致关闭一个可选能力会让其他来源也无法查询。

## 决策

Daily Agenda 始终由 Composition Root 创建，并独立判断 UserTask、Reminder、Waiting-For 与 Work Log 来源是否可用。

- 未启用的来源被视为不存在，不是查询失败；
- 已启用来源发生运行错误时，查询以显式 `FailureInfo` 失败关闭；
- Waiting-For 由其 canonical Service 提供，Agenda 不复制或修改领域真相；
- Waiting-For 的 `next_review_at` 映射为计划时间，`expected_by` 映射为到期时间；
- 到期复查或逾期等待映射为 `ATTENTION`，未来复查映射为 `ACTION`，已解决或取消映射为 `COMPLETED`；
- 同一 Waiting-For 在一个 Agenda 视图中只生成一个条目。

## 结果

Reminder/Scheduler 可以独立关闭而不阻断 UserTask、Waiting-For 或 Work Log 的 Agenda 查询。已启用来源的故障仍保持可观察、可诊断，不会被静默吞掉。

该决策不改变任何来源的持久化模型，也不声明跨数据库原子事务。

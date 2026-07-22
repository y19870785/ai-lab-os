# ADR-055 — Daily Agenda Optional-Source Composition

Status: Accepted

## 决策

Daily Agenda 始终由 canonical Composition Root 创建。UserTask、Reminder、Waiting-For 与 Work Log 是相互独立的可选来源：未启用能力不构成查询失败；已启用来源发生运行错误时，Agenda 通过显式 `FailureInfo` 失败关闭。

Agenda 只读取各 canonical domain，不复制或改写其状态真相。Waiting-For 的未来复查映射为 `ACTION`，到期复查或逾期等待映射为 `ATTENTION`，当天解决或取消映射为 `COMPLETED`；单个视图内每条 Waiting-For 最多产生一个 AgendaItem。

该决策不改变来源数据库，不创建跨数据库事务，也不新增第二份 Agenda 状态。

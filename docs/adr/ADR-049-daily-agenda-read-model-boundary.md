# ADR-049：Daily Agenda 读取模型边界

Status: Accepted

## 决策

`DailyAgendaService` 从既有 `ReminderInboxService`、`UserTaskService` 和
`MemoryManager` 读取，不引入新的权威来源或 Agenda 专用数据库。

## 后果

- 不新增 Agenda Table 或 Event Journal；
- View 按需计算；
- 跨 SQLite 聚合不是单一事务。

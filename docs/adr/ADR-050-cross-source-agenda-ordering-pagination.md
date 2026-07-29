# ADR-050：跨来源 Agenda 排序与分页

Status: Accepted

## 决策

所有来源都使用有界限制读取（Reminder：每页 100），归一化为 `AgendaItem`，再按
`effective_time`、`kind_priority`、`source_priority`、`source_id` 全局排序。排序后
应用候选上限 1200，最后对截断后的列表应用 `offset`/`limit`。

## 后果

- 排序稳定且不依赖来源读取顺序；
- 不是数据库 Snapshot，并发写入可能影响相邻页面；
- 深 offset 可能扫描更多来源页面。

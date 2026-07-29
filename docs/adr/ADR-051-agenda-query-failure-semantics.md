# ADR-051：Agenda 查询失败语义

Status: Accepted

## 决策

Reminder、UserTask 与 Work Log 来源分别独立查询。任一来源抛出异常时，返回
`agenda.query_failed`，并在 details 中包含 `failed_source`、`source_code` 与
`source_category`，不得返回部分结果。

## 后果

- 任一来源失败时失败关闭；
- 调用方收到一个带 `trace_id` 的结构化失败；
- 不得静默跳过失败来源。

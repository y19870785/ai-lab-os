# ADR-054 — Model Waiting-For as a Separate Canonical Domain

Status: Accepted

## 背景

UserTask 表示用户自己的行动，现有主状态为 `active`、`completed` 和 `cancelled`。等待他人回复或外部事件具有独立的复查时间、预期时间、催办历史、解决原因和重新打开语义。把这些语义塞进 UserTask 状态或 metadata 会混淆行动与外部依赖，并让 Agenda 和历史查询失去清晰真相源。

## 决策

1. 不增加 `UserTaskStatus.WAITING`。
2. Waiting-For 使用独立模型、Repository 和 Service，作为 canonical domain 管理自身生命周期。
3. Waiting-For 使用一等 `WorkspaceKey`；workspace 不是通用 metadata。
4. `due` 与 `overdue` 是根据时间计算的派生状态，不作为后台持续改写的持久化主状态。
5. 催办、延期、解决、取消和重新打开历史使用 append-only event。
6. UserTask、Reminder 与 Waiting-For 通过 ID 显式关联，不互相复制状态真相。
7. Daily Agenda 是跨来源 read model，不成为 Waiting-For 或其他来源的状态真相。
8. 独立数据库之间不声称原子事务；跨边界协调必须显式使用 Saga、幂等与 reconciliation。

## 后果

- UserTask 的现有状态机和 Schema 保持不变。
- Waiting-For 可以独立演化复查、催办和解决生命周期。
- Agenda 可以按来源能力进行可选聚合，同时保持已启用来源失败时的显式 `FailureInfo`。
- 新领域需要独立持久化、workspace 查询、并发控制、事件和 API/CLI 合同。
- 本决策不批准 SP-016 实现；具体 Composition Root 装配仍需在实现审查中确认。

## Agenda 决策边界

本 ADR 只确认 Agenda 是 read model。可选来源的具体 Composition Root 方案暂保留在 RFC-025；待 SP-016 实现审查确认后，再判断是否需要独立 ADR。本任务不创建第二份 Agenda ADR。

## 不包含

本决策不实现 Waiting-For 生产代码、数据库 Schema、API、CLI、CEO Assistant 意图、Inbox 转换、自动 Reminder、Scheduler 催办、外部通知或 Web UI。

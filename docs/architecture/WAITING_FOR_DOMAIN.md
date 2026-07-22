# Waiting-For Canonical Domain

## Domain 与状态机

`WaitingFor` 表示外部依赖，独立于表示用户行动的 `UserTask`。持久化主状态只有 `open`、`resolved`、`cancelled`；`due` 与 `overdue` 按 `expected_by`、`next_review_at` 和当前 Clock 派生。允许的操作是 create、follow-up、snooze、resolve、cancel、reopen，终态只能通过 reopen 回到 open。

## Schema、事务与历史

`followups.db` 由共享 `DatabaseManager` 管理，包含当前快照表与 append-only `WaitingForEvent` 表。create 与 created event、每次 CAS snapshot mutation 与对应 event 都在同一个显式 SQLite 事务内提交；失败时整体回滚，不产生孤立快照或事件。事件 sequence 与 snapshot revision 连续对应。

## Workspace 与并发

Repository 与 Service 的读写均显式接收一等 `WorkspaceKey`，空 tenant/workspace/namespace 规范化为 `default`。get、list、event history 和 mutation 都限定 workspace；跨 workspace 的精确读取返回安全 not-found。所有非 create mutation 必须携带 `expected_revision`，更新使用 compare-and-swap，冲突不会追加事件。

## API 与 CLI

FastAPI 在 `/waiting-for` 暴露 create、list、get、history、follow-up、snooze、resolve、cancel 与 reopen；workspace 只来自请求上下文。CLI 通过 `python -m cli waiting-for ...` 暴露相同生命周期。两者都从 `create_system` 得到同一个 canonical Service，不自行组装 Repository。

## Daily Agenda

Composition Root 无论 Reminder/Scheduler 是否启用都会创建 Waiting-For 与 Daily Agenda。Agenda 分别探测 UserTask、Reminder、Waiting-For、Work Log 可选来源；禁用来源不报错，已启用来源的运行错误以 `agenda.query_failed` 失败关闭。Waiting-For 的复查/期望时间映射为 ACTION 或 ATTENTION，resolved/cancelled 映射为 COMPLETED，Agenda 不复制领域真相。

## 失败语义

Service 将验证、not-found、revision/state conflict 和 persistence failure 映射到稳定 `FailureInfo`。EventBus 发布发生在数据库提交后；发布失败不会伪装事务失败，但会将 Waiting-For health 标记为 degraded。API 不返回 traceback、数据库路径或领域敏感内容。

## 显式排除

本领域不增加 `UserTaskStatus.WAITING`，不修改 UserTask/Reminder/Inbox schema，不自动创建 Reminder 或 Scheduler Job，不包含自然语言 Waiting-For 意图、Recurring Reminder、外部通知、Web UI、身份/RBAC、Knowledge 或跨数据库分布式事务。

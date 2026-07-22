# RFC-025 — Canonical Waiting-For Domain and Agenda Closure

Status: Proposed / Planning Baseline

## 背景

现有 canonical UserTask 的主状态只有 `active`、`completed` 和 `cancelled`。它描述用户自己需要采取的行动，无法准确表达等待他人回复、等待外部事件、何时再次检查、已经催办几次、对方回复后如何解决，以及等待事项如何显式转成用户的下一步行动。

SP-016 的规划目标是为这些外部依赖建立独立真相源，并让 Daily Agenda 在可选能力关闭时仍能聚合其他可用来源。本 RFC 只定义设计基线，不批准或实现 SP-016。

## 核心边界

Waiting-For 是独立 canonical domain，不通过增加 `UserTaskStatus.WAITING` 实现。

- UserTask 表示用户行动；Waiting-For 表示外部依赖。
- 二者的生命周期、终态和重新打开规则不同。
- Agenda 的展示与优先级语义不同。
- 催办历史不应污染 UserTask 的状态或 metadata。
- UserTask、Reminder 与 Waiting-For 之间的转换和追踪使用显式 ID 关联，不隐式改写彼此真相。

## 建议领域模型

设计草案 `WaitingFor`：

- `id`
- `workspace_key`
- `subject`
- `waiting_on`
- `context`
- `status`
- `expected_by`
- `next_review_at`
- `timezone`
- `linked_user_task_id`
- `linked_reminder_id`
- `source`
- `created_at`
- `updated_at`
- `resolved_at`
- `cancelled_at`
- `resolution_note`
- `metadata`
- `revision`

持久化主状态只允许 `open`、`resolved`、`cancelled`。`due` 和 `overdue` 根据当前时间、`expected_by` 与 `next_review_at` 计算，是查询期派生状态，不由后台任务持续改写。

## 历史模型

`WaitingForEvent` 是 append-only 历史。事件类型至少包括：

- `created`
- `followed_up`
- `snoozed`
- `resolved`
- `cancelled`
- `reopened`

事件记录应能回答上次何时催办、累计催办次数、延期原因以及最终如何解决。修订 WaitingFor 当前快照不得覆盖或删除既有事件。

## Workspace

每个 Waiting-For 与 Event 都必须使用一等 `WorkspaceKey`。Repository 和 Service 的 get、list 与 mutation 均显式接收 workspace；不得只把 workspace 放入通用 metadata，也不得把 workspace 当成可选展示字段。

## 持久化

建议使用独立 `followups.db`，并遵守以下边界：

- 通过现有 `DatabaseManager` 获取受管连接；
- 写操作使用显式事务；
- 使用 `revision` 做乐观并发控制；
- 所有查询和更新都按 workspace 限定；
- list 使用确定排序键和 stable pagination；
- 不修改现有 UserTask Schema；
- 跨 UserTask、Reminder 与 Waiting-For 数据库不声称原子事务，必要协调使用显式 Saga、幂等与 reconciliation。

## Service 生命周期

后续实现规划以下 canonical 操作：

- `create`
- `get`
- `list`
- `record_follow_up`
- `snooze`
- `resolve`
- `cancel`
- `reopen`

Service 合同必须为创建与重复 mutation 定义确定性幂等边界；明确 resolved/cancelled 终态的编辑限制和 reopen 前置条件；使用 expected revision 检测冲突；把验证、not-found、workspace、revision 与 persistence 失败映射到 `FailureInfo`；在事务提交后发布 EventBus 事件；复用现有递归敏感 metadata 检查，禁止凭据进入 metadata、事件或错误响应。

## Agenda 集成

Daily Agenda 必须先成为可选来源聚合器：

- UserTask 可用时读取 UserTask；
- Reminder 可用时读取 Reminder；
- Waiting-For 可用时读取 Waiting-For；
- Work Log 可用时读取 Work Log。

能力未启用不视为查询失败，Agenda 继续聚合其余来源。已启用的数据源发生运行错误时，继续使用显式 `FailureInfo` 失败关闭，不静默返回不完整成功。

Waiting-For 到 Agenda 的建议映射：

- `next_review_at` 到期：`ATTENTION`
- `expected_by` 超期：`ATTENTION`
- 未来 `next_review_at`：`ACTION / NEXT`
- `resolved`：`COMPLETED`
- `cancelled`：`COMPLETED`

Agenda 是 read model，不复制、不持久化或改写 Waiting-For 的状态真相。

## API 和 CLI 草案

本 RFC 只设计，不新增 Router 或 CLI 命令。

建议 API：

```text
POST   /waiting-for
GET    /waiting-for
GET    /waiting-for/{id}
POST   /waiting-for/{id}/follow-ups
POST   /waiting-for/{id}/snooze
POST   /waiting-for/{id}/resolve
POST   /waiting-for/{id}/cancel
POST   /waiting-for/{id}/reopen
```

建议 CLI：

```text
python -m cli waiting-for create
python -m cli waiting-for list
python -m cli waiting-for show
python -m cli waiting-for follow-up
python -m cli waiting-for snooze
python -m cli waiting-for resolve
```

API 与 CLI 后续必须从 canonical Composition Root 获取同一个 Service，不得自行组装 Repository。

## 明确排除

SP-016 不包含：

- CEO Assistant 自然语言 Waiting-For 意图；
- Unified Inbox Waiting-For 转换；
- 自动创建 Reminder；
- Scheduler 自动催办；
- Recurring Reminder；
- 企业微信、邮件、短信或推送；
- Web UI；
- Work Log 查询重构；
- Knowledge；
- 用户身份、RBAC 或多租户；
- 跨数据库分布式事务。

## 验收设计

SP-016 后续实现至少需要证明：

1. 创建 Waiting-For；
2. 持久化并在进程重启后恢复；
3. workspace 隔离；
4. stable list pagination；
5. revision conflict；
6. follow-up event append-only；
7. snooze；
8. resolve、cancel 与 reopen；
9. Agenda due、overdue 与 completed 映射；
10. Reminder/Scheduler 关闭时 Agenda 仍可读取其他来源；
11. API 和 CLI 使用 canonical Composition Root；
12. 不使用 LLM 输出冒充持久化成功。

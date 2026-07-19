# RFC-024：Unified Inbox and Capture-to-Action

Status: Proposed

## 问题

用户经常需要先可靠保存一条尚未明确分类的事项。直接猜测并创建 Task、Reminder 或 Work Log 会把不确定性变成业务写入风险。

## 目标

- 先捕获为 workspace 隔离的 `InboxItem`
- 由显式 API、CLI 或产品操作触发转化
- 支持转化为 UserTask、Reminder、Work Log 或轻量 Note
- 保留原始内容、来源和目标对象 ID
- 重复转化不创建第二个目标对象
- list/get 保持只读

## 非目标

- 不做全自动 AI 分类或执行
- 不新增 Follow-up、Waiting For、Recurring Reminder 等领域
- 不建设知识发布、Web UI、OCR、文件上传或多租户重构
- 不改变 UserTask、Reminder、Work Log 的既有业务语义

## 领域模型

`InboxItem` 包含：ID、`WorkspaceKey`、内容、来源、状态、可选建议类型、UTC 时间、解析类型、解析目标 ID、元数据和 revision。

状态仅有：

- `pending`
- `resolved`
- `dismissed`

建议类型只是展示提示，MVP 默认 `unknown`，不会触发业务写入。

## 持久化

新增独立 `inbox.db`，包含用户可见状态表 `inbox_items` 与内部 Saga 表 `inbox_resolution_claims`，通过 `DatabaseManager` 的 lease 使用连接。查询以 tenant、workspace、namespace 三元组过滤，并按 `created_at DESC, id DESC` 稳定排序。

索引覆盖：

- workspace + status + created_at + id
- 非空 `resolved_target_id`
- resolution claim 的 workspace + state + updated_at

## 跨进程解析权

任何 Task、Reminder 或 Work Log 写入之前，Repository 必须在 SQLite `BEGIN IMMEDIATE` transaction 中校验 workspace、验证 pending 状态并创建以 Inbox Item ID 为主键的唯一 claim。

claim 记录唯一 `resolved_type`、确定性 target key/ID 以及 `claimed → target_created → completed` 状态。不同类型请求不能取得已有 claim，因此不得调用目标 Service。同类型请求可以恢复未完成 claim；Inbox 状态与 claim completed 最终在同一 SQLite transaction 中提交。

进程内锁仅是减少重复工作的优化，不承担跨 worker、CLI 或 API 进程的一致性职责。

## 应用边界

唯一 Composition Root 创建并注入 `SQLiteInboxRepository` 与 `InboxService`。API、CLI 和 CEO Assistant 不自行创建数据库连接或 Store。

解析路径复用现有正式服务：

- UserTask：`UserTaskService`
- Reminder：`NaturalLanguageReminderOrchestrator`
- Work Log：`MemoryManager` 的 Episodic Memory 写入路径
- Note：仅更新 Inbox 解析状态，不建立新领域

UserTask 与 Work Log 通过确定性目标 ID 恢复；Reminder 通过确定性 orchestrator idempotency key 恢复。进程在 claim 或目标创建后崩溃时，后续同类型请求继续相同 Saga，不需要删除持久化记录。

## 失败语义

对外使用 `FailureInfo`，主要错误码为：

- `inbox.not_found`
- `inbox.invalid_content`
- `inbox.invalid_status`
- `inbox.already_resolved`
- `inbox.resolve_failed`
- `inbox.workspace_mismatch`

数据库路径、SQL、堆栈和密钥不得进入 API 响应。

## 可观测性

发布 `inbox.captured`、`inbox.resolved`、`inbox.dismissed` 与 `inbox.resolve_failed`。事件只记录标识符、workspace、来源和状态，不携带完整捕获文本。

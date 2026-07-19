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

新增独立 `inbox.db` 和 `inbox_items` 表，通过 `DatabaseManager` 的 lease 使用连接。查询以 tenant、workspace、namespace 三元组过滤，并按 `created_at DESC, id DESC` 稳定排序。

索引覆盖：

- workspace + status + created_at + id
- 非空 `resolved_target_id`

## 应用边界

唯一 Composition Root 创建并注入 `SQLiteInboxRepository` 与 `InboxService`。API、CLI 和 CEO Assistant 不自行创建数据库连接或 Store。

解析路径复用现有正式服务：

- UserTask：`UserTaskService`
- Reminder：`NaturalLanguageReminderOrchestrator`
- Work Log：`MemoryManager` 的 Episodic Memory 写入路径
- Note：仅更新 Inbox 解析状态，不建立新领域

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

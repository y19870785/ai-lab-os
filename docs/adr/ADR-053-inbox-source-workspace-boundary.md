# ADR-053：Inbox Source and Workspace Boundary

Status: Proposed

## 决策

所有 Inbox Service 操作必须显式接收 `WorkspaceKey`。空字符串组件在服务边界规范化为既有 canonical default workspace；`None` 不是合法 workspace 参数。

持久化的每个查询和更新都使用 tenant、workspace、namespace 三元组过滤。ID 在其他 workspace 存在时返回 `inbox.workspace_mismatch`，不得读取、解析或 dismiss 该记录。

## 来源

MVP 的正式来源为：

- `api`
- `cli`
- `ceo_assistant`

来源字段允许未来扩展，但必须是非空、长度受限的字符串。来源只用于追溯，不授予权限，也不触发自动分类或转化。

## 入口约束

- API 复用既有 Bearer Token、CORS 与 Workspace header/context
- CLI 使用 `WorkspaceKey()` 的 canonical default workspace
- CEO Assistant 使用 `ApplicationRequest.workspace_key`
- 三个入口共享 Composition Root 注入的同一个 `InboxService`

## 目标对象 workspace

- UserTask 在既有 metadata workspace 中保留作用域
- Reminder 复用现有 orchestrator 的 workspace scope 与 workspace metadata
- Work Log 在既有内容 metadata 中记录 workspace ID

## 后果

- 不同 workspace 无法查看或转化彼此 Inbox Item
- 默认 workspace 行为与 Reminder、Daily Agenda 和既有 CLI 一致
- 本 ADR 不引入新的鉴权体系或多租户模型

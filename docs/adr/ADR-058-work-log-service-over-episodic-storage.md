# ADR-058：基于既有 Episodic Storage 的 WorkLogService

Status: Accepted

> 这是 SP-018 规划基线的 Accepted 架构决策，不批准或启动产品实施。

## 背景

Work Log 当前通过通用 `MemoryManager` 读写，物理 Row 已位于
`episodic.db / episodic_memories`。产品消费方需要类型安全的 Workspace、ID、过滤、
排序、分页与 legacy 语义。新建 `work_logs.db` 会分裂权威来源，并要求 Migration 或双写。

## 决策

1. `WorkLogService` 是 Work Log create/get/list 的唯一逻辑产品边界；
2. `WorkLogRepository` protocol 与 SQLite adapter 访问既有 `episodic_memories` Table；
3. Adapter 使用组合根现有 `DatabaseManager` 及其 `episodic` 连接所有权；
4. 不创建 `work_logs.db`、新 Table、跨数据库事务或重复 Work Log Row；
5. 入口迁移后，只有 `WorkLogService` 可写入 `content.type=work_log`；
6. 新写入只允许 insert，不使用 `INSERT OR REPLACE` 覆盖既有 canonical ID；
7. `SQLiteEpisodicStore` 仍是通用 Episodic Memory Store；Adapter 可以共享 Row codec，
   但不引入第二个 Work Log 权威来源；
8. 在 Projection 或分页前，Repository SQL 必须应用完整 WorkspaceKey 与
   `type=work_log` predicate；
9. SP-018 规划假定无 Schema 变更；任何 Index 或 Table 变更都需要独立证据和批准。

## 后果

- CEO Assistant、API、CLI、Inbox、Agenda 与 Brief 共享一个产品合同；
- 不把通用 `MemoryQuery` 扩展为 Work Log 专用产品 API；
- 两个 Adapter 访问同一 Table，必须明确所有权，并以测试证明没有双写或破坏性替换；
- 没有新 Index 时 JSON 过滤可能较慢；本地优先 Alpha 边界优先保证正确性与 Workspace 隔离。

## 拒绝的替代方案

### 仅继续使用 MemoryManager

拒绝，因为它会把 Work Log 专用 Workspace、canonical ID、legacy Projection、Context
Reference 与分页推入通用 Memory 抽象，而该抽象当前按 importance 截断与排序。

### 创建 work_logs.db

拒绝，因为会引入第二权威来源、Migration 负担、重复风险和跨数据库协调。

### 把 legacy Row 复制为新的 canonical 表示

拒绝，因为自动 Migration 可能造成重复、Identity 漂移、Workspace 误分配和破坏性回滚。

## 产品实施边界

本 ADR 只记录决策。规划基线不实现 Repository、Service、Query、Schema、组合根或产品代码。

# UserTask 架构

## 领域边界

- **UserTask**：用户可见的待办、承诺和工作事项，由 `core/user_tasks` 管理。
- **Execution Task**：`core/task` 中执行 Workflow 的内部运行任务，不承载用户待办。
- **Scheduled Job**：`core/scheduler` 的定时执行基础设施。
- **Reminder**：未来把 UserTask 与 Scheduled Job 连接的提醒领域，SP-004 不实现。

## 数据流

```mermaid
flowchart TD
    API["Task API"] --> Service["UserTaskService"]
    CEO["CEO Assistant"] --> Service
    Service --> Repository["SQLiteUserTaskRepository"]
    Repository --> Lease["DatabaseManager ConnectionLease"]
    Lease --> DB["sqlite/tasks.db"]
    Service --> Bus["EventBus"]
```

`tasks.db` 位于统一 `sqlite_dir`。Repository 只借用 DatabaseManager 管理的连接，不关闭借用连接；写操作使用事务并在异常时回滚。更新采用 `revision` 乐观并发，过期写入返回冲突。

## 生命周期

持久化状态为 `active`、`completed`、`cancelled`。`overdue` 根据 active 状态、UTC 截止时间和当前时间派生，不写入数据库。重复完成或取消同一终态是幂等操作；completed 与 cancelled 之间直接切换是冲突；显式 `reopen()` 可恢复为 active。

## 历史兼容

`UserTaskService.import_legacy()` 是显式、非破坏的迁移入口。它只读取 Decision Memory 中 `type=task` 的记录，以旧记录 ID 生成稳定任务 ID；重复执行不会重复导入，原记录不删除、不修改。损坏记录计入失败并使 Health degraded，但不阻断正常记录。

## 已知限制

- SP-004 不实现 Reminder Trigger 或 UserTask-Scheduler Bridge。
- CEO Assistant 只解析“今天/明天”这类确定日期；无法可靠识别的日期不会伪造截止时间。
- 当前并发控制是单记录 revision 乐观锁，不提供跨任务事务。

# ADR-029：Memory SQLite 连接所有权

## 状态

Accepted for SP-003 implementation branch

## 背景

三个 SQLite Memory Store 可以接收 `DatabaseManager`，但旧实现会在每次操作后无条件关闭连接。若直接注入 Manager，Store 会关闭 borrowed connection，而 Manager 仍缓存该失效对象。Composition Root 同时使用不同目录创建 Manager 和 Store，存在生成第二套空数据库的风险。

## 决策

1. `DatabaseManager` 是 Managed Mode 下 Memory SQLite 共享连接的唯一 Owner。
2. Store 必须通过显式 `ConnectionLease` 区分 owned 与 borrowed connection。
3. Store 不关闭 borrowed connection；`Store.close()` 在 Managed Mode 中不关闭 Manager 资源。
4. 未注入 Manager 时使用 Standalone Mode，operation-scoped owned connection 由 lease 关闭。
5. Composition Root 将三个既有 `settings.sqlite_dir/*.db` 路径显式绑定到同一个 Manager。
6. 同一逻辑名在一个 Manager 实例中禁止重绑到不同路径。
7. `close()` 或 `close_all()` 后允许后续显式请求开启新连接生命周期，绝不返回旧失效对象。
8. 写操作显式 commit/rollback；`batch_save` 保持单事务原子性。

## 结果

- Manager 与 Store 的关闭责任可由代码验证，而非依赖注释。
- 现有 Memory 数据路径和 Schema 保持不变。
- Standalone Store API 保持兼容。
- Knowledge 与 Scheduler SQLite 所有权不在 SP-003 中迁移，后续如需统一必须另行设计。

# ADR-029：Memory SQLite 连接所有权

## 状态

Accepted

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
9. Managed lease 在完整借用周期持有对应逻辑数据库的 `RLock`；`close()` 和 `close_all()` 必须等待活跃 lease 退出。
10. 锁顺序固定为 per-database lock 后全局注册锁，不在持有全局注册锁时执行 SQL 或等待数据库锁，不同逻辑数据库保持并发。
11. 连接仅在关闭成功后从 Manager 缓存移除；关闭失败必须保留引用并允许后续重试。
12. `close_all()` 尝试快照中的全部连接后统一报告失败，成功项移除，失败项继续受 Manager 管理。

## 结果

- Manager 与 Store 的关闭责任可由代码验证，而非依赖注释。
- 现有 Memory 数据路径和 Schema 保持不变。
- Standalone Store API 保持兼容。
- Managed lease 的公开抽象本身保护借用周期，Store 和调用者不再需要额外获取 Manager 锁。
- 当前仍依赖上层在 shutdown 前停止新请求，SP-003 不增加全局请求闸门。
- Knowledge 与 Scheduler SQLite 所有权不在 SP-003 中迁移，后续如需统一必须另行设计。

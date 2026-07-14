# AI-Lab Memory SQLite 连接所有权

> SP-003 状态：Completed
>
> Merge PR：#5 · 合并方式：Squash Merge · 审查结论：APPROVED
> SP-003 Merge Commit：`ce3655ff5f7a625da6b168058873dadfc2289b5f` · 合并时间：`2026-07-14T19:59:33Z`

本文定义 `DatabaseManager` 与 Episodic、Semantic、Decision 三个 SQLite Memory Store 的连接所有权。目标是消除共享连接被 Store 关闭、失效连接留在缓存以及数据库路径漂移的问题。

## 所有权模型

### Managed Mode

- Composition Root 创建进程内唯一 `DatabaseManager`。
- 三个 Memory Store 接收同一个 Manager，并按逻辑数据库名借用连接。
- Manager 是共享连接的唯一 Owner，负责创建、探针、关闭和缓存移除。
- Store 通过 `ConnectionLease` 使用 borrowed connection；managed lease 在完整借用周期持有对应逻辑数据库的 `RLock`，退出时释放锁但不关闭连接。
- `Store.close()` 在 Managed Mode 中是幂等空操作，最终由 `DatabaseManager.close_all()` 关闭连接。

### Standalone Mode

- 未注入 Manager 时，Store 保留独立使用方式。
- Store 为每次操作创建 owned connection。
- `ConnectionLease` 退出时关闭 owned connection。
- Standalone Store 不共享连接，也不改变现有构造参数和 MemoryStore API。

## Lease 边界

`ConnectionLease` 显式携带 `owned` 状态：

```text
owned=True  -> lease 退出时关闭连接
owned=False -> lease 进入时取得数据库锁，退出时释放锁但不关闭连接
```

Managed lease 在 `__enter__()` 取得 per-database lock，并在锁内延迟获取连接；`__exit__()` 在正常或异常路径都会释放锁。这样 `close()` 和 `close_all()` 必须等待活跃 lease 退出，不能提前关闭 borrowed connection。Store 不再额外获取 Manager 锁，Managed 与 Standalone 的释放行为由 lease 统一表达。

## 路径绑定

Composition Root 显式绑定：

```text
episodic -> settings.sqlite_dir/episodic.db
semantic -> settings.sqlite_dir/semantic.db
decision -> settings.sqlite_dir/decision.db
```

同一 Manager 实例中，同一逻辑数据库名不得绑定到不同路径。路径冲突必须抛出明确异常。SP-003 不迁移、不重命名、不删除数据库文件，也不修改 Schema。

## 生命周期

```text
SystemContainer.start
  -> Store.initialize
  -> DatabaseManager.lease
  -> 创建或复用共享连接

SystemContainer.shutdown
  -> Store.close（不关闭 borrowed connection）
  -> DatabaseManager.close_all（统一关闭并清空）
```

`close(name)` 等待活跃 lease 退出，确认连接关闭成功后才从缓存移除。关闭失败时异常向上传播，连接仍由 Manager 跟踪，后续调用可以重试。旧连接成功关闭后不可使用；再次 `get_connection()` 会开启该逻辑数据库的新连接生命周期。

`close_all()` 对连接快照逐一调用 `close()`。单个失败不会阻止其他连接的关闭；全部尝试结束后统一报告失败。成功关闭的连接被移除，失败连接继续受 Manager 跟踪并可在后续 `close_all()` 中重试。

## 事务与锁

- 每个逻辑数据库拥有独立 `RLock`，全局注册锁只保护路径、连接和锁注册表。
- 锁顺序固定为 per-database lock -> 全局注册锁；代码不会在持有全局注册锁时等待数据库锁。
- managed lease 从进入到退出持续持有 per-database lock，因此同一数据库的 SQL、关闭和连接替换互斥；不同逻辑数据库仍可并发。
- SQL 不在持有全局注册锁时执行。
- 写操作在单个数据库锁内执行，成功 commit，异常 rollback。
- `batch_save` 使用一个 lease 和一个事务，任一项失败时整体 rollback。
- 读操作不 commit。
- 使用 `RLock` 避免同一线程中的事务辅助逻辑递归锁死。
- 保持 `check_same_thread=False`、`sqlite3.Row`、WAL 与 `busy_timeout=5000`。

## 失败与 Health

- 路径冲突、连接失败、SQL/事务失败必须抛出，不返回 Fake Success。
- rollback 和 close 失败不被吞掉；关闭失败的连接保留在 Manager 中供后续重试。SystemContainer 清理阶段统一记录异常，并继续给其他组件清理机会，不向 API 暴露路径或 SQL 细节。
- `DatabaseManager.health()` 只探针已经打开的连接，不创建新数据库；使用 `SELECT 1`，不 commit、不改变事务。
- System Health 根据 Manager 生命周期和探针结果报告 `healthy`、`not_initialized`、`failed` 或 `stopped`，并沿用统一 `RuntimeStatus` / `FailureInfo`。

## 范围边界

Knowledge SQLite Store 继续使用 operation-scoped owned connection；SchedulerPersistence 继续持有并关闭自己的连接。本轮不迁移它们，也不处理 backup/restore、Schema、Reminder、Knowledge Reindex、自动 Tool Calling 或 Coordination 扩展。

当前 `SystemContainer` 依赖上层先停止请求，再进入 shutdown；本轮没有新增可阻止任意外部持有 Store 引用继续借用连接的全局数据库闸门。

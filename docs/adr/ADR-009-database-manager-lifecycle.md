# ADR-009：Database Manager 生命周期

## 状态

Accepted（2026-07-12）

## 背景

在 v0.13.0 之前，`SQLiteEpisodicStore`、`SQLiteSemanticStore` 和
`SQLiteDecisionStore` 分别管理 SQLite 连接，每次方法调用都会打开和关闭连接。这会
造成三份重复连接代码、每次 `save()` 都创建新文件描述符、缺少集中式 Schema Migration，
以及无法形成一致的备份与恢复策略。

## 决策

通过 `get_db()` 获取的单例 `DatabaseManager` 负责全部 SQLite 连接生命周期：

| 职责 | 所有者 |
| --- | --- |
| 创建连接与连接池 | `DatabaseManager` |
| 单数据库锁 | `DatabaseManager.get_lock(name)` |
| Schema Migration（DDL） | `DatabaseManager` 与 `migration.py` |
| 健康检查 | `DatabaseManager.health_check(name)` |
| Vacuum | `DatabaseManager.vacuum(name)` |
| 备份与恢复 | `DatabaseManager`，当前仅定义接口 |
| 事务管理 | `DatabaseManager` 与 `connection.transaction()` |

Memory Store 使用 `db_manager.get_connection(name)`，不得直接调用 `sqlite3.connect()`。
为兼容旧调用，当 `db_manager=None` 时 Store 仍可回退到自行管理连接。

## 后果

- 三个 SQLite Store 接受可选的 `db_manager` 参数；
- 数据库文件统一位于 `data/`；
- Schema 变更通过 `run_migration()`，不再分散到 Store 初始化逻辑；
- `DatabaseManager` 增加 `health_check()` 与 `vacuum()`；
- `backup()` 与 `restore()` 仍为 `NotImplemented` stub，但接口合同已经存在。

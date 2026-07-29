# ADR-008：统一 Memory API

## 状态

Accepted（2026-07-12）

## 背景

AI-Lab Memory Layer 包含 Session、Episodic、Semantic 和 Decision 四类 Memory。它们
分别在 2.2 至 2.6 阶段开发，导致不同 Store 的 API 略有差异。

## 决策

所有 Memory Store 必须实现 `MemoryStore` protocol 定义的相同八方法接口：

| 方法 | 签名 | 语义 |
| --- | --- | --- |
| `save` | `(item: MemoryItem) -> str` | 保存单个对象并返回 ID |
| `batch_save` | `(items: list[MemoryItem]) -> list[str]` | 批量保存并返回 ID |
| `get` | `(id: str) -> MemoryItem | None` | 按 ID 读取 |
| `query` | `(spec: MemoryQuery) -> list[MemoryItem]` | 按条件查询 |
| `delete` | `(id: str) -> bool` | 按 ID 删除并返回是否成功 |
| `count` | `(filter: MemoryFilter | None) -> int` | 使用可选过滤器计数 |
| `initialize` | `() -> None` | 幂等初始化 Store |
| `close` | `() -> None` | 幂等释放资源 |

采用该接口的理由：

- Store 不得额外暴露其他 Store 缺少的方法；高层 API 的类型专用便利封装除外；
- `count()` 必须应用 `filter`，此前 SessionMemory、Semantic 和 Decision 忽略该参数；
- `initialize()` 确保 SQLite Store 在使用前建表；SessionMemory 为 no-op；
- 即使连接由 DatabaseManager 管理，也需要 `close()` 表达资源生命周期。

## 后果

- 四个 Store 统一暴露八个公开方法；
- `MemoryQuery` 增加用于分页的 `offset`、`sort_by` 和 `sort_desc`；
- `MemoryFilter` 删除 `tags`，相关条件移入 `MemoryQuery.filters`；
- 现有调用方保持兼容；
- 不同 Store 的测试接口保持一致。

## 已考虑的替代方案

- **保留不对称接口**：拒绝。调用方将被迫在调用前检查 `isinstance()`，违反 LSP；
- **拆分多个 protocol**：拒绝。四个 Store 共享大部分语义，统一 protocol 更清晰。

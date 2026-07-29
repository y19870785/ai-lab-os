# AI-Lab 历史技术债登记

> 最后更新：2026-07-12｜版本：v0.14.0。本文件是历史快照；当前技术债以
> `project_state.json` 与 `docs/project/TECHNICAL_DEBT.md` 为准。

## 当时的未解决技术债

### TD-002：MemoryManager 双 API（P1）

- **状态：** Deferred
- **说明：** `MemoryManager` 同时有新 API（`save_memory/retrieve_memory/...`）与
  Legacy API（`save/retrieve/...`）。旧 API 已标记 deprecated，但测试仍在使用。
- **建议动作：** 将测试迁移到新 API，并在 v0.15.0 删除旧 API。
- **文件：** `core/memory/manager.py`、`tests/core/memory/test_memory.py`、
  `tests/core/memory/test_integration.py`

### TD-003：SessionMemory 作为 MemoryStore（P1）

- **状态：** Deferred
- **说明：** `SessionMemory` 实现 `MemoryStore` protocol，但使用不持久化、不分布式的
  内存 Dict。多实例部署需要持久化 Backend。
- **建议动作：** 在 v0.16.0 重命名为 `SessionCache` 或增加 SQLite/Redis Backend。
- **文件：** `core/memory/session.py`

### TD-004：ConsolidationEngine 单线程瓶颈（P1）

- **状态：** Deferred
- **说明：** `ConsolidationEngine._consolidate_store()` 顺序遍历全部对象，达到
  100k+ 时可能阻塞。
- **建议动作：** 在 v0.16.0 增加每批 100 个对象的异步分批处理。
- **文件：** `core/memory/consolidation.py`

### TD-005：MemorySnapshot 全量扫描比较（P2）

- **状态：** Deferred
- **说明：** `compare_snapshot()` 拉取全部对象（`top_k=10000`）并在内存执行 O(n) Diff。
- **建议动作：** 增加增量 Diff 或 Checksum。
- **文件：** `core/memory/snapshot.py`

### TD-006：Event Handler 异常被吞掉（P2）

- **状态：** Deferred
- **说明：** `MemoryPublisher` 使用 `asyncio.gather(return_exceptions=True)`，异常被
  静默丢弃，应写入 `system.error` Topic。
- **文件：** `core/bus/publisher.py`

### TD-007：Config Model 不匹配（P2）

- **状态：** Deferred
- **说明：** `core/config.py` 的 `DatabaseConfig` 包含 PostgreSQL Field，但
  `DatabaseManager` 使用 SQLite，应对齐或拆分配置对象。
- **文件：** `core/config.py`、`core/database/manager.py`

### TD-008：Audit Lambda Closure（P3）

- **状态：** Deferred
- **说明：** `MemoryAuditor` 通过带默认参数的 Lambda 捕获 Closure；虽然可用，但
  `functools.partial` 更易读。
- **文件：** `core/memory/audit.py`

### TD-009：Knowledge Layer Stub（P1）

- **状态：** Deferred
- **说明：** 当时 `knowledge/manager.py` 与 `knowledge/ingestion.py` 仍为 Skeleton。
- **文件：** `knowledge/*.py`

### TD-010：缺少 Provider Layer（P0，阻塞当时 Phase 3）

- **状态：** Must address before Phase 3
- **说明：** 当时没有统一 Model/Embedding/Vector/Storage Provider 抽象。
- **建议动作：** 在 v0.15.0、开始 Knowledge Layer 前创建 `core/providers/`。
- **文件：** 架构级问题

## 当时已解决的技术债

### TD-001：test_episodic.py 语法错误

- **状态：** ✅ Resolved in v0.13.0
- **解决记录：** 测试文件以清晰语法重写，当时 121 个测试全部通过。

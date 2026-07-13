# ADR-006: Knowledge 存储策略

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 006                                  |
| **标题**     | Knowledge 存储策略                     |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-004                              |
| **取代**     | —                                    |

## 1. 背景

Knowledge Layer 需要管理五种知识类型，每种类型的存储需求不同：

| 知识类型   | 存储需求                         | 检索需求               |
| ---------- | -------------------------------- | ---------------------- |
| 文档       | 全文存储 + 块存储 + 向量索引      | 关键词 + 向量 + 混合   |
| 实体       | 属性存储 + 向量索引               | ID 查找 + 向量相似     |
| 关系       | 图结构存储                        | 图遍历                 |
| 经验       | 文档存储 + 向量索引               | 语义检索               |
| 决策       | 文档存储 + 向量索引               | 语义检索 + 时间线      |

需要确定 Phase 1 的存储选型策略：在"零外部依赖"和"生产可用"之间做 trade-off。

## 2. 决策

### 2.1 总体策略：分层存储 + 统一抽象

所有存储后端通过 `knowledge/storage/protocol.py` 抽象接口访问，Phase 1 采用轻量级实现：

```
存储抽象层 (KnowledgeStore / VectorStore / GraphStore)
        │
        ├── Document Store → SQLite（结构化） + 文件系统（原始文件）
        ├── Entity Store   → SQLite
        ├── Relation Store → SQLite（递归 CTE 做图遍历）
        ├── Vector Store   → Chroma（与 Memory Layer 共用实例）
        └── Full-Text Search → SQLite FTS5（关键词检索）
```

### 2.2 各存储后端选型理由

**Document Store：SQLite + File System**

SQLite 存储文档元数据和结构化字段，原始文件存文件系统。

| 存储内容     | 存储位置              | 原因                             |
| ------------ | --------------------- | -------------------------------- |
| 文档元数据   | SQLite `documents` 表  | 结构化查询（按标签/作者/时间筛选） |
| Chunk 内容   | SQLite `chunks` 表     | 块级检索，SQL FTS5 关键词匹配     |
| 原始文件     | 文件系统 `data/docs/`  | 大文件（PDF/图片）不适合存数据库   |
| 全文索引     | SQLite FTS5 虚拟表     | 内置关键词检索，零依赖             |

**Entity Store + Relation Store：SQLite**

Phase 1 直接用 SQLite 存储实体和关系，通过 `WITH RECURSIVE` 做有限深度图遍历。

```sql
-- 实体表
CREATE TABLE entities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    attributes TEXT,        -- JSON
    description TEXT,
    embedding BLOB,
    access_level TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- 关系表
CREATE TABLE relations (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES entities(id),
    target_id TEXT NOT NULL REFERENCES entities(id),
    relation_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    attributes TEXT,        -- JSON
    created_at TEXT
);

-- 图遍历示例：从实体 e1 出发，2 层深度
-- WITH RECURSIVE path AS (
--   SELECT source_id, target_id, 1 AS depth FROM relations WHERE source_id = 'e1'
--   UNION ALL
--   SELECT r.source_id, r.target_id, p.depth + 1
--   FROM relations r JOIN path p ON r.source_id = p.target_id
--   WHERE p.depth < 2
-- ) SELECT * FROM path;
```

当数据量 > 10 万节点或需要更复杂的图算法时，Phase 2 升级到 Neo4j 或 NetworkX。

**Vector Store：Chroma（与 Memory Layer 共用）**

原因已在 ADR-003 中讨论。Knowledge Layer 在 Chroma 中用不同 collection 隔离：

```
collection "memory_episodic"   ← Memory Layer
collection "memory_semantic"   ← Memory Layer
collection "knowledge_doc"     ← Knowledge Layer: 文档 chunks
collection "knowledge_entity"  ← Knowledge Layer: 实体
collection "knowledge_exp"     ← Knowledge Layer: 经验知识
collection "knowledge_decision"← Knowledge Layer: 决策知识
```

**Full-Text Search：SQLite FTS5**

Python 内置 sqlite3 支持 FTS5 扩展，无需额外依赖。

```sql
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    content,                    -- 搜索字段
    document_id UNINDEXED,       -- 过滤字段（不参与全文索引）
    tokenize='unicode61'        -- 支持中文
);
```

### 2.3 Knowledge 与 Memory 的存储关系

```
Memory Layer                      Knowledge Layer
─────────────                      ─────────────
                                   Chroma collection
Chroma collection                    "knowledge_doc"
  "memory_episodic"                  "knowledge_entity"
  "memory_semantic"                  "knowledge_exp"
                                     "knowledge_decision"

SQLite: entity + relation表  ←可选同步→   SQLite: entities + relations 表
(系统自动提取，低置信度)                  (用户管理，高置信度)
```

两个层**不共享**同一个表/集合，而是通过事件或定期同步机制做可选双向更新。

**为什么不直接共享？** 生命周期不同——Memory 的语义实体是临时的（可能 TTL 过期后被遗忘），Knowledge 的实体是用户管理的（需要手动删除）。共享会导致意外丢失或产生脏数据。

## 3. 后果

### 正面

- Phase 1 零外部依赖即可运行完整的 Knowledge Layer
- FTS5 提供内建全文检索，无需 Elasticsearch
- Chroma 集合隔离，Memory 和 Knowledge 互不干扰
- 所有存储通过抽象接口访问，Phase 2 替换后端不影响上层

### 负面

- SQLite 的图遍历性能有限（深度 > 3 层的递归查询可能较慢）
- Chroma collection 数量多时需要连接池管理
- SQLite 的并发写入性能在分布式场景下不足

### 风险

- SQLite 文件可能随知识量增长迅速膨胀
  - **缓解**：原始文件存文件系统，SQLite 只存元数据和 chunks（元数据 vs 内容分离）
- FTS5 中文分词较基础（unicode61 tokenizer）
  - **缓解**：中文场景下关键词检索只作兜底，主要靠向量检索

## 4. 理由

**核心原则**：Phase 1 项目尚在 Foundation 阶段，最大风险是"不工作"，不是"不够快"。

选择 SQLite + Chroma + File System 三驾马车的原因：
1. 全部零外部依赖安装（Python 内置 / pip install）
2. CI/CD 无需启动外部服务
3. 新贡献者 clone 即用
4. 后期升级路径明确：SQLite → PostgreSQL/Neo4j，File System → S3/MinIO

## 5. 相关链接

- [RFC-004 §3.4 模块 4](docs/rfc/004-knowledge-layer-architecture.md#模块-4embedding-interface向量化接口)
- [ADR-003: Memory Layer 技术选型](docs/adr/ADR-003-memory-layer-tech-stack.md)
- [ADR-004: Memory 数据模型与持久化](docs/adr/ADR-004-memory-data-model.md)

# ADR-003: Memory Layer 技术选型

## Metadata

| Field        | Value                                |
| ------------ | ------------------------------------ |
| **ADR 编号** | 003                                  |
| **标题**     | Memory Layer 技术选型                  |
| **状态**     | 已接受                                |
| **作者**     | Lin Yuyan                            |
| **创建日期** | 2026-07-12                           |
| **更新日期** | 2026-07-12                           |
| **关联 RFC** | RFC-002                              |
| **取代**     | —                                    |

## 1. 背景

Memory Layer 需要三个存储后端来支撑不同记忆类型：
- **KV 存储**：会话级短时记忆，要求低延迟、支持 TTL
- **向量存储**：情景记忆的语义检索
- **关系/图存储**：语义记忆的实体关系查询

需要在"零外部依赖"和"生产可用"之间做 trade-off。

## 2. 决策

### 2.1 KV 存储：Python dict（Phase 1）→ Redis（Phase 2）

Phase 1 直接使用 `dict[str, SessionMemory]` + `asyncio` 定时扫描做 TTL 清理。

理由：
- 单进程开发阶段无外部依赖
- Session Memory 数据量小（同时活跃的会话数通常 < 100）
- Redis 配置和运维成本在当前阶段不划算

Phase 2 切换到 Redis 时，接口不变，替换 `session.py` 内部实现即可。

### 2.2 向量存储：Chroma（Phase 1）→ 可选升级

选用 Chroma 而非其他向量数据库的原因：

| 方案       | 部署模式     | 持久化     | Phase 1 阶段 |
| ---------- | ------------ | ---------- | ------------ |
| Chroma     | 嵌入式/客户端 | 本地文件   | ✅ 零运维     |
| Milvus     | 独立服务     | 依赖 etcd  | ❌ 太重       |
| Qdrant     | 独立服务     | 本地文件   | ⚠️ 需要 Docker |
| FAISS      | 内存索引     | 需自行管理  | ⚠️ 无持久化   |

Chroma 在 Phase 1 的优势：
- `pip install chromadb` 即可使用，零配置
- 支持 embedding 自动计算（可选），也可我们自行提供
- 持久化到本地文件，进程重启不丢数据
- 提供集合（Collection）隔离不同记忆空间

### 2.3 关系/图存储：SQLite（Phase 1）→ 可选升级

Phase 1 用 SQLite 两张表（entity + relation）存储语义记忆。

理由：
- Python 内置 sqlite3，零依赖
- Entity-Relation 查询在数据量 < 10 万时 SQL 完全够用
- `with recursive` 支持有限深度的图遍历
- 后续可以升级到 NetworkX（纯内存图分析）或 Neo4j（分布式图数据库）

### 2.4 Embedding 模型

Phase 1 使用外部 embedding API（模型不可知），接口定义为：

```python
class Embedder(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

用户可以通过配置项 `memory.embedding.provider` 切换：
- `"openai"`: OpenAI Embedding API
- `"ollama"`: 本地 Ollama 模型
- `"none"`: 跳过 embedding（退化到纯关键词检索）

## 3. 后果

### 正面

- Phase 1 无外部依赖即可运行 Memory Layer
- 所有存储后端通过抽象接口注入，切换成本低
- Chroma 和 SQLite 都是零运维方案

### 负面

- 内存 KV 会在进程重启后丢失会话记忆（情景/语义记忆在 Chroma+SQLite 中不受影响）
- SQLite 不适合高并发图遍历（但 Phase 1 单进程无此问题）
- Chroma 在数据量 > 100 万条时性能下降（Phase 1 远达不到这个量级）

### 风险

- Chroma 社区版更新频繁，需要锁定版本
- Embedding API 网络延迟可能影响 Agent 启动速度（可在后台异步预加载）

## 4. 理由

**核心原则**：Phase 1 追求"可用"而不是"最优"。

选择这些技术栈的最关键原因是——它们让 Memory Layer 在零外部依赖的情况下即可工作。这对于一个尚在 Foundation 阶段的项目来说是决定性的：降低了新贡献者的门槛，也降低了 CI/CD 的复杂度和测试成本。

## 5. 相关链接

- [RFC-002: Memory Layer Architecture](docs/rfc/002-memory-layer-architecture.md)
- [ADR-004: Memory 数据模型与持久化](docs/adr/ADR-004-memory-data-model.md)
